"""Regression gates for batch progress: stale/manual flags must not imply playability."""
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image
from tools.turnaround_gate import capture, approve

from tools.character_pipeline import PipelineError, record_path, fingerprint
from tools.genshin_batch import seed, status, probe_asset


class GenshinStatusSafetyTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.workspace = Path(temp.name) / "workspace"

    def test_unseeded_status_is_read_only(self):
        report = status(self.workspace, ("xiao",))
        self.assertEqual(report["counts"]["total"], 1)
        self.assertEqual(report["counts"]["seeded"], 0)
        self.assertEqual(report["characters"][0]["stage"], "not_seeded")
        self.assertFalse(report["characters"][0]["playable_role_verified"])
        self.assertFalse(self.workspace.exists())

    def test_seeded_case_reports_no_playability_or_license(self):
        seed(self.workspace, ("xiao",))
        path = record_path(self.workspace, "genshin_xiao_main")
        before = path.read_bytes()
        row = status(self.workspace, ("xiao",))["characters"][0]
        self.assertTrue(row["case_exists"])
        self.assertEqual(row["stage"], "awaiting_local_artwork")
        self.assertFalse(row["playable_role_verified"])
        self.assertFalse(row["redistribution_verified"])
        self.assertEqual(path.read_bytes(), before)

    def test_unverified_source_cannot_be_overridden_by_qa_flags(self):
        seed(self.workspace, ("xiao",))
        path = record_path(self.workspace, "genshin_xiao_main")
        data = json.loads(path.read_text(encoding="utf-8"))
        data["status"] = "qa_reviewed"
        data["qa"]["visual_pass"] = True
        data["qa"]["runtime_pass"] = True
        data["rights"]["local_use"] = True
        data["rights"]["redistribution"] = True
        data["rights"]["reviewer"] = "test person"
        data["rights"]["evidence"] = "test evidence"
        role = self.workspace / "build" / "fake-role"
        role.mkdir(parents=True)
        data["build"]["role"] = str(role)
        path.write_text(json.dumps(data), encoding="utf-8")
        row = status(self.workspace, ("xiao",))["characters"][0]
        self.assertFalse(row["playable_role_verified"])
        self.assertFalse(row["redistribution_verified"])
        self.assertGreater(row["blocking_issue_count"], 0)

    def test_mismatched_identity_is_rejected(self):
        seed(self.workspace, ("xiao",))
        path = record_path(self.workspace, "genshin_xiao_main")
        data = json.loads(path.read_text(encoding="utf-8"))
        data["profile"] = "genshin_hu_tao"
        path.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaisesRegex(PipelineError, "identity/profile mismatch"):
            status(self.workspace, ("xiao",))

    def test_linked_cases_directory_is_not_followed(self):
        with tempfile.TemporaryDirectory() as other:
            self.workspace.mkdir(parents=True)
            try:
                (self.workspace / "cases").symlink_to(
                    Path(other), target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("Symlink creation unavailable")
            with self.assertRaisesRegex(PipelineError, "Linked cases/reviews"):
                status(self.workspace, ("xiao",))


    def test_mutated_built_role_invalidates_recorded_qa(self):
        seed(self.workspace, ("xiao",))
        path = record_path(self.workspace, "genshin_xiao_main")
        data = json.loads(path.read_text(encoding="utf-8"))
        source = self.workspace / "synthetic-original.zip"
        source.write_bytes(b"synthetic source")
        role = self.workspace / "build" / "genshin_xiao_main" / "ChibiPipelineRole"
        role.mkdir(parents=True)
        art = role / "synthetic.png"
        art.write_bytes(b"pre-QA")
        data["source"]["local_asset"] = str(source)
        data["source"]["sha256"] = fingerprint(source)
        data["rights"].update({
            "reviewer": "test reviewer", "evidence": "local synthetic permission",
            "local_use": True,
        })
        data["status"] = "qa_reviewed"
        reference = self.workspace / "synthetic-turnaround"
        reference.mkdir()
        for i, key in enumerate(("front", "side", "back")):
            Image.new("RGB", (120, 160), (50 * (i + 1), 70, 100)).save(
                reference / (key + ".png"))
        views = capture(
            *(reference / (key + ".png") for key in ("front", "side", "back")),
            reference_url="https://artist.example/synthetic-xiao-three-views",
            artist="Synthetic artist", variant="Test v1")
        data["turnaround"] = approve(
            views, "Synthetic reviewer",
            dict.fromkeys(("silhouette", "outfit", "identity", "cross_view"), True),
            "2026-10-28")
        data["build"]["role"] = str(role)
        data["qa"].update({
            "visual_pass": True, "runtime_pass": True,
            "asset_sha256": fingerprint(role),
        })
        path.write_text(json.dumps(data), encoding="utf-8")
        self.assertTrue(status(self.workspace, ("xiao",))["characters"][0]
                        ["playable_role_verified"])
        art.write_bytes(b"changed after QA")
        self.assertFalse(status(self.workspace, ("xiao",))["characters"][0]
                         ["playable_role_verified"])

    def test_corrupt_native_zip_has_controlled_error(self):
        asset = self.workspace / "corrupt.zip"
        asset.parent.mkdir(parents=True)
        asset.write_bytes(b"not a zip archive")
        with self.assertRaisesRegex(PipelineError, "Invalid or unsupported"):
            probe_asset(asset)

if __name__ == "__main__":
    unittest.main()

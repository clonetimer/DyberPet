"""R6: paired benchmark must be fair, asset-private and fail closed."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.benchmark_creator_asset_backends import paired_creator_audit
from tools.install_artist_codex import REPO, REVISION, SOURCES


class CreatorAuditBenchmarkTests(unittest.TestCase):
    def setUp(self):
        holder = tempfile.TemporaryDirectory(prefix="rust-r6-fake-")
        self.addCleanup(holder.cleanup)
        self.root = Path(holder.name)
        self.role = self.root / "SourceCodexNahida"
        (self.role / "action").mkdir(parents=True)
        source_id = SOURCES["nahida"][0]
        self.receipt = self.role / "PERSONAL_IMPORT.json"
        self.receipt.write_text(json.dumps({
            "source_repository": REPO, "source_commit": REVISION,
            "source_id": source_id, "selected_profile": SOURCES["nahida"][2],
        }), encoding="utf8")
        self.geometry = self.role / "IMPORT_REPORT.json"
        self.geometry.write_text(json.dumps({
            "preserve_source_frames": True,
            "source_pixel_integrity_verified": True,
            "aligned_frames_per_action": {},
        }), encoding="utf8")
        self.seen = []

    def worker(self, role, character, mode, rounds, warmup):
        self.assertEqual(role, self.role)
        self.assertEqual(character, "Nahida")
        self.assertEqual(rounds, 2)
        self.assertEqual(warmup, 1)
        self.seen.append(mode)
        return {"available": True, "backend": {"active": mode},
                "report_sha256": "b" * 64,
                "audit_median_ms": 10 if mode == "python" else 5,
                "process_elapsed_ms": 100 if mode == "python" else 105,
                "import_elapsed_ms": 10,
                "rss_after_bytes": 50000000 if mode == "python" else 51000000,
                "python_alloc_peak_bytes": 20000}

    def test_counterbalanced_8_processes_and_equal_role_reports(self):
        result = paired_creator_audit(
            self.root, "nahida", blocks=2, rounds=2,
            warmup=1, runner=self.worker)
        self.assertEqual(self.seen, ["python", "rust", "rust", "python",
                                     "rust", "python", "python", "rust"])
        self.assertTrue(result["report_parity"])
        self.assertEqual(result["measured_speedup"], 2)
        self.assertEqual(result["backends"]["rust"]["processes"], 4)
        self.assertEqual(result["backends"]["python"]["audit_median_ms"], 10)
        self.assertEqual(result["backends"]["rust"]["audit_median_ms"], 5)
        self.assertEqual(result["scope"], "creator_role_audit_only_not_animation_fps")
        self.assertNotIn(str(self.root), json.dumps(result))

    def test_changed_report_must_block_unsupported_speedup_claim(self):
        def drift(role, character, mode, rounds, warmup):
            result = self.worker(role, character, mode, rounds, warmup)
            if len(self.seen) == 4:
                result["report_sha256"] = "e"*64
            return result
        with self.assertRaisesRegex(RuntimeError, "reports differ"):
            paired_creator_audit(self.root, "nahida", blocks=1,
                                 rounds=2, warmup=1, runner=drift)

    def test_broken_native_cannot_silently_claim_speedup(self):
        def missing(role, character, mode, rounds, warmup):
            if mode == "rust":
                return {"available": False, "backend": {"active":"python"}}
            return self.worker(role, character, mode, rounds, warmup)
        with self.assertRaisesRegex(RuntimeError, "unavailable"):
            paired_creator_audit(self.root, "nahida", blocks=1,
                                 rounds=2, warmup=1, runner=missing)
        report = paired_creator_audit(
            self.root, "nahida", blocks=1, rounds=2,
            warmup=1, runner=missing, require_rust=False)
        self.assertIsNone(report["measured_speedup"])
        self.assertIsNone(report["report_parity"])

    def test_role_receipt_mismatch_or_unpinned_conversion_refused(self):
        self.receipt.write_text('{"selected_profile":"genshin_klee"}',
                                encoding="utf8")
        with self.assertRaisesRegex(ValueError, "pinned"):
            paired_creator_audit(self.root, "nahida", runner=self.worker)
        self.receipt.write_text(json.dumps({
            "source_repository": REPO, "source_commit": REVISION,
            "source_id": SOURCES["nahida"][0],
            "selected_profile": SOURCES["nahida"][2]}), encoding="utf8")
        self.geometry.write_text(json.dumps({
            "preserve_source_frames": False,
            "source_pixel_integrity_verified": True,
            "aligned_frames_per_action": {}}))
        with self.assertRaisesRegex(ValueError, "pinned"):
            paired_creator_audit(self.root, "nahida", runner=self.worker)

    def test_invalid_pairs_and_unsupported_character_refused(self):
        with self.assertRaisesRegex(ValueError, "Blocks"):
            paired_creator_audit(self.root, "nahida", blocks=0,
                                 runner=self.worker)
        with self.assertRaisesRegex(ValueError, "no supported character"):
            paired_creator_audit(self.root, "raiden", runner=self.worker)

    def test_symlinked_role_refused_when_supported(self):
        link_root = self.root / "other"
        link_root.mkdir()
        link = link_root / self.role.name
        try:
            link.symlink_to(self.role, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("Platform disallows symlink creation")
        with self.assertRaisesRegex(ValueError, "linked"):
            paired_creator_audit(link_root, "nahida", runner=self.worker)


if __name__ == "__main__":
    unittest.main()

"""Doro is the ONLY character allowed to enter a completed-art gate in R51.

No copyrighted Doro graphics are stored in or synthesized by these tests.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.doro_single_role_gate import audit_doro, audit_doro_live2d, main, REFERENCE_URL


class DoroOneAtATimeGateTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.role = self.root / "SourceDoro"
        self.role.mkdir()
        (self.role / "pet_conf.json").write_text("{}", encoding="utf-8")
        (self.role / "act_conf.json").write_text("{}", encoding="utf-8")

    def _receipt(self, name, content):
        (self.role / name).write_text(json.dumps(content), encoding="utf-8")

    def test_legacy_installed_doro_does_not_count_as_completed(self):
        row = audit_doro(self.role)
        self.assertEqual(row["role"], "Doro")
        self.assertFalse(row["complete"])
        self.assertFalse(row["source_reference_recognized"])
        self.assertFalse(row["independent_threeview_candidate"])
        self.assertFalse(row["manual_visual_and_windows_approved"])
        self.assertGreaterEqual(len(row["blockers"]), 3)

    def test_approved_style_reference_alone_cannot_pass_without_original_views(self):
        self._receipt("DORO_SOURCE.json", {
            "schema_version": 1, "character": "Doro",
            "accepted_visual_reference": REFERENCE_URL,
            "accepted_visual_creator": "0x4682B4",
            "body_type": "quadruped", "artist": "example illustrator",
            "art_variant": "same hand-drawn set", "not_a_legacy_approximation": True,
        })
        row = audit_doro(self.role)
        self.assertTrue(row["source_reference_recognized"])
        self.assertFalse(row["complete"])
        self.assertIn("Missing three independently declared", "\n".join(row["blockers"]))

    def test_forged_review_flags_still_fail_without_art_and_live_actions(self):
        self._receipt("DORO_HUMAN_ACCEPTANCE.json", {
            "schema_version": 1, "reviewer": "sample QA operator",
            "review_notes": "SYNTHETIC fixture, NEVER a real approved artwork",
            "same_character_all_views": True, "original_character_likeness": True,
            "four_leg_gait": True, "native_interactions": True,
            "windows_real_desktop": True,
            "art_use_and_distribution_permission": True,
        })
        row = audit_doro(self.role)
        self.assertFalse(row["complete"])
        self.assertFalse(row["source_reference_recognized"])
        self.assertFalse(row["independent_threeview_candidate"])

    def test_old_source_receipt_must_not_be_promoted_by_guessing(self):
        self._receipt("DORO_SOURCE.json", {
            "schema_version": 1, "character": "Doro",
            "accepted_visual_reference": REFERENCE_URL,
            "accepted_visual_creator": "0x4682B4",
            "body_type": "quadruped",
            "artist": "old art creator", "art_variant": "r7-classic",
            "not_a_legacy_approximation": True,
        })
        self.assertFalse(audit_doro(self.role)["source_reference_recognized"])

    def test_cli_read_only_and_strict_status(self):
        before = {f.name: f.read_bytes() for f in self.role.iterdir()}
        report = self.root / "doro-status.json"
        self.assertEqual(main(["--role", str(self.role), "--out", str(report)]), 0)
        self.assertEqual(main(["--role", str(self.role),
                               "--require-complete"]), 1)
        self.assertEqual(before, {f.name: f.read_bytes() for f in self.role.iterdir()})
        self.assertFalse(json.loads(report.read_text(encoding="utf-8"))["complete"])

    def test_valid_local_live2d_inventory_is_not_a_finished_doro(self):
        model_dir = self.root / "Cubism"
        model_dir.mkdir()
        for name in ("Doro.moc3", "texture.png", "Idle.motion3.json"):
            (model_dir / name).write_bytes(b"TEST_FIXTURE_NO_REAL_DORO")
        path = model_dir / "Doro.model3.json"
        path.write_text(json.dumps({
            "FileReferences": {
                "Moc": "Doro.moc3", "Textures": ["texture.png"],
                "Motions": {"Idle": [{"File": "Idle.motion3.json"}]}
            }
        }), encoding="utf-8")
        before = {p.name: p.read_bytes() for p in model_dir.iterdir()}
        result = audit_doro_live2d(path)
        self.assertTrue(result["source_model_installed"])
        self.assertEqual(result["model_inventory"]["motion_groups"], {"Idle": 1})
        self.assertFalse(result["complete"])
        self.assertFalse(result["independent_threeview_complete"])
        self.assertFalse(result["art_redistribution_permission_verified"])
        self.assertEqual(main(["--live2d-model", str(path), "--require-complete"]), 1)
        self.assertEqual(before, {p.name: p.read_bytes() for p in model_dir.iterdir()})

    def test_missing_live2d_model_fails_closed_without_modifying_files(self):
        output = audit_doro_live2d(self.root / "not-installed.model3.json")
        self.assertFalse(output["source_model_installed"])
        self.assertFalse(output["complete"])
        self.assertIn("Local model cannot be verified", output["blockers"][0])

    def test_missing_role_is_explicitly_blocked(self):
        report = audit_doro(self.root / "does-not-exist")
        self.assertFalse(report["complete"])
        self.assertEqual(report["blockers"], ["No real installed Doro role directory"])


if __name__ == "__main__":
    unittest.main()

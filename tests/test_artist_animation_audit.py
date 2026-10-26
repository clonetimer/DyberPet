"""Creator-frame pixel QA measures structure, not character likeness."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image
from tools.artist_animation_audit import audit_native_character


class OriginalArtPixelAuditTests(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.TemporaryDirectory()
        self.addCleanup(self.work.cleanup)
        self.role = Path(self.work.name) / "SourceArtist"
        (self.role / "action").mkdir(parents=True)
        self.set_config({"idle": {"images": "idle"},
                         "right_walk": {"images": "walk", "need_move": True}})
        self.frame("idle", 0, (40, 60, 80, 255))
        self.frame("walk", 0, (70, 60, 80, 255))
        self.frame("walk", 1, (20, 140, 30, 255))
        (self.role / "PERSONAL_IMPORT.json").write_text(
            '{"selected_profile":"genshin_kaveh"}', encoding="utf-8")

    def frame(self, action, i, color):
        path = self.role / "action" / f"{action}_{i}.png"
        Image.new("RGBA", (40, 55), color).save(path, format="PNG")
        return path

    def set_config(self, act):
        (self.role / "pet_conf.json").write_text(
            json.dumps({"default": "idle"}), encoding="utf-8")
        (self.role / "act_conf.json").write_text(
            json.dumps(act), encoding="utf-8")

    def test_independent_original_frame_motion_counts_do_not_claim_likeness(self):
        before = {p.name: p.read_bytes() for p in (self.role / "action").iterdir()}
        result = audit_native_character(self.role)
        self.assertEqual(result["source_status"],
                         "import_receipt_present_not_likeness_proof")
        self.assertTrue(result["summary"]["animation_structure_passed"])
        self.assertEqual(result["summary"]["native_actions"], 2)
        self.assertEqual(result["summary"]["original_frames_inspected"], 3)
        self.assertFalse(result["summary"]["character_visual_likeness_verified"])
        self.assertFalse(result["summary"]["action_semantics_manually_verified"])
        self.assertEqual(result["actions"][1]["pixel_unique_frame_count"], 2)
        self.assertEqual(before, {p.name: p.read_bytes()
                                  for p in (self.role / "action").iterdir()})
        self.assertFalse((self.role / "ACTION_PIXEL_AUDIT.json").exists())

    def test_identical_walk_frames_are_flagged_without_rewriting_art(self):
        self.frame("walk", 1, (70, 60, 80, 255))
        result = audit_native_character(self.role)
        walk = next(x for x in result["actions"] if x["action"] == "right_walk")
        self.assertIn("movement_has_no_distinct_frames", walk["issues"])
        self.assertIn("all_frames_visually_identical", walk["issues"])
        self.assertFalse(result["summary"]["animation_structure_passed"])

    def test_transparent_or_inconsistent_frames_are_visible_in_audit(self):
        self.frame("walk", 0, (0, 0, 0, 0))
        path = self.role / "action" / "walk_1.png"
        Image.new("RGBA", (50, 51), (20, 140, 30, 255)).save(path, format="PNG")
        result = audit_native_character(self.role)
        self.assertIn("fully_transparent_frames",
                      result["summary"]["issue_categories"])
        self.assertIn("inconsistent_frame_dimensions",
                      result["summary"]["issue_categories"])

    def test_missing_sequences_and_unsafe_symlinks_are_rejected(self):
        (self.role / "action" / "walk_1.png").rename(
            self.role / "action" / "walk_3.png")
        with self.assertRaisesRegex(ValueError, "Frames missing"):
            audit_native_character(self.role)
        with tempfile.TemporaryDirectory() as td:
            alias = Path(td) / "linked_role"
            try:
                alias.symlink_to(self.role, target_is_directory=True)
            except (OSError, NotImplementedError):
                return
            with self.assertRaisesRegex(ValueError, "linked"):
                audit_native_character(alias)

    def test_original_demo_never_counts_as_verified_creator_identity(self):
        (self.role / "BUILTIN_CHIBI_DEMO.json").write_text("{}", encoding="utf-8")
        result = audit_native_character(self.role)
        self.assertEqual(result["source_status"], "builtin_demo_not_original_art")
        self.assertFalse(result["summary"]["character_visual_likeness_verified"])


if __name__ == "__main__":
    unittest.main()

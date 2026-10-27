"""R8: source-anchored appearance cues never auto-approve a character."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from tools.creator_reference_cues import REVIEWED_EXAMPLES, cues_for_local_role, cue_text


class CreatorIdentityCueTests(unittest.TestCase):
    def test_three_real_inspected_upstream_source_files_have_distinct_sha_anchors(self):
        self.assertEqual(set(REVIEWED_EXAMPLES), {
            "genshin_nahida", "genshin_xiao", "genshin_wanderer"})
        hashes = [x["source_png_git_blob"] for x in REVIEWED_EXAMPLES.values()]
        self.assertEqual(len(set(hashes)), 3)
        self.assertTrue(all(len(x) == 40 for x in hashes))
        self.assertTrue(all(x["look_for"] for x in REVIEWED_EXAMPLES.values()))

    def test_known_persona_is_a_prompt_not_visual_grade(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            role = root / "ArtistRole"
            role.mkdir()
            with patch("tools.genshin_library._profile_of",
                       return_value="genshin_nahida"):
                result = cues_for_local_role(root, "ArtistRole")
            self.assertEqual(result["name"], "纳西妲")
            self.assertFalse(result["original_likeness_automatically_approved"])
            self.assertFalse(result["all_actions_visually_checked"])
            self.assertIn("绿色", cue_text(result))

    def test_full_roster_templates_can_offer_unapproved_source_bound_checklists(self):
        from tools.genshin_roster import GENSHIN_ROSTER
        self.assertEqual(len(GENSHIN_ROSTER), 123)
        with TemporaryDirectory() as td:
            root = Path(td)
            (root / "ArtistLocal").mkdir()
            for character in ("barbara", "ayaka", "varka", "xilonen"):
                with self.subTest(character=character), patch(
                        "tools.genshin_library._profile_of",
                        return_value="genshin_" + character):
                    cues = cues_for_local_role(root, "ArtistLocal")
                    self.assertEqual(
                        cues["checklist_origin"],
                        "roster_template_not_independent_png_inspection")
                    self.assertEqual(cues["profile"], "genshin_" + character)
                    self.assertTrue(cues["look_for"])
                    self.assertIsNone(cues["reference"])
                    self.assertIsNone(cues["inspected_png_git_blob"])
                    self.assertFalse(cues["original_likeness_automatically_approved"])
                    self.assertIn("未直接检视", cue_text(cues))

    def test_direct_png_example_does_not_upgrade_other_local_versions(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            (root / "ArtistLocal").mkdir()
            with patch("tools.genshin_library._profile_of",
                       return_value="genshin_xiao"):
                cues = cues_for_local_role(root, "ArtistLocal")
                self.assertEqual(
                    cues["checklist_origin"],
                    "one_independently_opened_pinned_source_png_example")
                self.assertTrue(cues["reference_is_an_example_not_a_exact_version_match"])
                self.assertFalse(cues["original_likeness_automatically_approved"])
                self.assertIn("本机版本仍须逐帧", cue_text(cues))

    def test_unknown_identity_and_generated_demo_never_get_cues(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            role = root / "Example"
            role.mkdir()
            with patch("tools.genshin_library._profile_of",
                       return_value="genshin_unsupported"):
                self.assertIsNone(cues_for_local_role(root, "Example"))
            (role / "BUILTIN_CHIBI_DEMO.json").write_text("{}", encoding="utf-8")
            with patch("tools.genshin_library._profile_of",
                       return_value="genshin_nahida"):
                self.assertIsNone(cues_for_local_role(root, "Example"))
            self.assertIn("逐帧检查", cue_text(None))

    def test_reject_path_traversal(self):
        with TemporaryDirectory() as td:
            with self.assertRaisesRegex(ValueError, "Invalid installed role"):
                cues_for_local_role(Path(td), "../escape")


if __name__ == "__main__":
    unittest.main()

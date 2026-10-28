"""R28: Diona is a VERIFIED SOURCE, never a preinstalled/approved sprite."""
from __future__ import annotations
import ast
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tools.character_source_coverage import source_coverage
from tools.creator_art_preference import source_style, install_preference
from tools.personal_source_batch import plan_personal_sources, INSTALLERS


class DionaCatalogTests(unittest.TestCase):
    def test_123_roster_and_69_accurate_pinned_profiles(self):
        ledger = source_coverage()
        s = ledger["summary"]
        self.assertEqual(s["template_count"], 123)
        self.assertEqual(s["characters_with_pinned_sources"], 69)
        self.assertEqual(s["characters_without_pinned_sources"], 54)
        self.assertEqual(s["pinned_source_options"], 93)
        diona = next(x for x in ledger["characters"] if x["id"] == "genshin_diona")
        self.assertTrue(diona["source_found"])
        self.assertEqual(diona["name"], "迪奥娜")
        self.assertFalse(diona["installed"])
        self.assertFalse(diona["visual_likeness_qa_passed"])
        self.assertFalse(diona["rights_verified"])
        self.assertEqual(diona["source_candidate_count"], 1)
        asset = diona["source_candidates"][0]
        self.assertEqual(asset["provider"], "gmcy_diona")
        self.assertEqual(asset["source_key"], "diona_170")
        self.assertEqual(asset["original_author_frames"], 170)
        self.assertEqual(asset["verified_original_git_blob_count"], 170)
        self.assertEqual(asset["original_creator_action_groups"], 9)
        self.assertFalse(asset["source_author_likeness_qa_passed"])
        self.assertFalse(asset["prebundled_original_art"])

    def test_opt_in_batch_plan_identifies_diona_without_downloading(self):
        self.assertIn("gmcy_diona", INSTALLERS)
        self.assertEqual(install_preference("gmcy_diona_original"), 1)
        self.assertEqual(source_style("gmcy_diona")["visual_qa_status"], "pending_human_review")
        with TemporaryDirectory() as folder:
            plan = plan_personal_sources(Path(folder) / "fresh")
        s = plan["summary"]
        self.assertEqual(s["selected_profiles"], 123)
        self.assertEqual(s["ready_for_opt_in"], 69)
        self.assertEqual(s["missing_source"], 54)
        role = next(x for x in plan["characters"] if x["profile"] == "genshin_diona")
        self.assertEqual(role["status"], "ready_for_opt_in")
        self.assertEqual(role["provider"], "gmcy_diona")
        self.assertEqual(role["source_key"], "diona_170")
        self.assertFalse(role["original_likeness_verified"])

    def test_real_character_picker_and_async_worker(self):
        source = (Path(__file__).resolve().parents[1] /
                  "DyberPet/DyberSettings/CharCardUI.py").read_text("utf-8")
        ast.parse(source)
        self.assertIn('mode="gmcy_diona_original"', source)
        self.assertIn('elif self.mode == "gmcy_diona_original":', source)
        self.assertIn('if mode == "gmcy_diona_original":', source)
        self.assertIn('return "genshin_diona"', source)
        self.assertIn('install_gmcy_diona(', source)
        self.assertIn('确认仅在本机导入为新的独立角色吗', source)


if __name__ == "__main__":
    unittest.main()

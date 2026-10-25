"""Provenance-only React-Shimeji leads must never count as installed/approved."""
from __future__ import annotations

import ast
from pathlib import Path
import unittest

from tools.react_shimeji_source_leads import (
    CANDIDATES, REPOSITORY, REVISION, react_shimeji_lead_report)
from tools.character_source_coverage import source_coverage


class ReactShimejiLeadTests(unittest.TestCase):
    def test_six_profiles_retain_lfs_leads_two_now_have_new_verified_zip_alternatives(self):
        report = react_shimeji_lead_report()
        self.assertEqual(report["summary"]["repo_character_packages"], 2224)
        self.assertEqual(report["summary"]["matched_distinct_genshin_personas"], 6)
        self.assertEqual(report["summary"]["new_leads_for_missing_characters"], 3)
        self.assertTrue(report["summary"]["fixed_source_coverage_unchanged"])
        self.assertEqual(report["summary"]["downloaded_or_installed"], 0)
        self.assertEqual(report["summary"]["art_qa_passed"], 0)
        self.assertEqual(set(CANDIDATES), {
            "genshin_alhaitham", "genshin_amber", "genshin_columbina",
            "genshin_fischl", "genshin_freminet", "genshin_kaveh"})
        for entry in report["characters"]:
            self.assertEqual(
                entry["existing_fixed_source"],
                entry["id"] in {"genshin_alhaitham", "genshin_kaveh", "genshin_freminet"})
            self.assertEqual(entry["status"], "lfs_pointer_verified_art_uninspected")
            self.assertFalse(entry["native_role_installed"])
            self.assertFalse(entry["full_lfs_art_downloaded_and_hashed"])
            self.assertFalse(entry["visual_likeness_qa_passed"])
            self.assertFalse(entry["redistribution_rights_verified"])
            self.assertEqual(len(entry["lfs_content_sha256_expected"]), 64)
            self.assertEqual(len(entry["lfs_pointer_git_blob_sha"]), 40)
            self.assertIn(REPOSITORY, entry["source_url"])
            self.assertIn(REVISION, entry["source_url"])
        self.assertIsNone(next(x for x in report["characters"] if x["id"] == "genshin_amber")["preview_url"])
        self.assertIsNotNone(next(x for x in report["characters"] if x["id"] == "genshin_kaveh")["preview_url"])

    def test_existing_pinned_source_counts_remain_intact(self):
        summary = source_coverage()["summary"]
        self.assertEqual(summary["characters_with_pinned_sources"], 43)
        self.assertEqual(summary["characters_without_pinned_sources"], 80)
        self.assertEqual(summary["pinned_source_options"], 66)

    def test_gui_has_explicit_safe_preview_choices_and_no_auto_download(self):
        source = (Path(__file__).resolve().parents[1] /
                  "DyberPet/DyberSettings/character_catalog_dialog.py").read_text("utf-8")
        ast.parse(source)
        self.assertIn("from tools.react_shimeji_source_leads import", source)
        self.assertIn("profile in REACT_CANDIDATES", source)
        self.assertIn("QInputDialog.getItem", source)
        self.assertIn("QDesktopServices.openUrl(QUrl(url))", source)
        self.assertIn("Git LFS 动画候选（原文件待核验）", source)


if __name__ == "__main__":
    unittest.main()

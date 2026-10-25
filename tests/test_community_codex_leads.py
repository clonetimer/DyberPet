"""Unreviewed online role leads cannot inflate pinned art or installed counts."""
from __future__ import annotations

import ast
from pathlib import Path
import unittest

from tools.community_codex_leads import PROFILE_TO_SLUG, public_candidate_report
from tools.character_source_coverage import source_coverage


class CommunityRoleLeadsTests(unittest.TestCase):
    def test_35_gallery_entries_yield_only_13_still_unpinned_role_leads(self):
        report = public_candidate_report()
        summary = report["summary"]
        self.assertEqual(summary["public_entries_in_collection"], 35)
        self.assertEqual(summary["entries_mapped_to_roster"], 33)
        self.assertEqual(summary["excluded_nonroster_variants"], 2)
        self.assertEqual(summary["new_leads_for_previously_missing_characters"], 13)
        self.assertTrue(summary["pinned_source_coverage_is_unchanged"])
        self.assertEqual(summary["art_likeness_approved"], 0)
        self.assertEqual(summary["added_to_installed_roles"], 0)
        for row in report["characters"]:
            self.assertEqual(row["status"], "candidate_unverified")
            self.assertFalse(row["source_asset_files_downloaded_and_hashed"])
            self.assertFalse(row["likeness_manually_reviewed"])
            self.assertFalse(row["distributable"])
            self.assertTrue(row["candidate_url"].startswith("https://codexpetdb.com/en/pets/"))
        pinned = source_coverage()["summary"]
        self.assertEqual(pinned["characters_with_pinned_sources"], 47)
        self.assertEqual(pinned["characters_without_pinned_sources"], 76)
        self.assertEqual(pinned["pinned_source_options"], 70)

    def test_names_are_correct_and_nonroster_manekina_is_excluded(self):
        self.assertEqual(PROFILE_TO_SLUG["genshin_kaveh"], "gi-kaveh")
        self.assertEqual(PROFILE_TO_SLUG["genshin_kinich"], "gi-kinich")
        self.assertEqual(PROFILE_TO_SLUG["genshin_kirara"], "gi-kirara")
        self.assertNotIn("genshin_manekina", PROFILE_TO_SLUG)
        self.assertEqual(len(PROFILE_TO_SLUG), len(set(PROFILE_TO_SLUG.values())))

    def test_gui_only_opens_known_candidates_by_explicit_click(self):
        path = Path(__file__).resolve().parents[1] / "DyberPet/DyberSettings/character_catalog_dialog.py"
        source = path.read_text(encoding="utf-8")
        ast.parse(source)
        self.assertIn("self.communityButton.clicked.connect(self._open_community_candidate)", source)
        self.assertIn("if profile in PROFILE_TO_SLUG:", source)
        self.assertIn("QDesktopServices.openUrl(QUrl(", source)
        self.assertIn("社区图集候选（未审核）", source)


if __name__ == "__main__":
    unittest.main()

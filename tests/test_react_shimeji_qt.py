"""Real offscreen Qt candidate browser: no source is downloaded automatically."""
from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
try:
    from PySide6.QtWidgets import QApplication
except ImportError:
    QApplication = None


@unittest.skipIf(QApplication is None, "PySide6 optional; runs in Qt loader CI")
class ReactShimejiCatalogQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from DyberPet.DyberSettings.character_catalog_dialog import CharacterCatalogDialog
        from tools.character_progress import character_progress
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        report = character_progress(Path(self.tmp.name) / "roles")
        self.assertEqual(report["summary"]["template_total"], 125)
        self.dialog = CharacterCatalogDialog(report)
        self.addCleanup(self.dialog.close)
        self.dialog.familyFilter.setCurrentIndex(
            self.dialog.familyFilter.findData("genshin"))

    def test_new_unverified_lead_filter_has_31_distinct_missing_profiles(self):
        self.dialog.statusFilter.setCurrentIndex(
            self.dialog.statusFilter.findData("lead"))
        self.assertEqual(self.dialog.results.count(), 31)
        self.assertIn("31 / 125", self.dialog.countLabel.text())
        names = [self.dialog.results.item(i).data(0x0100)
                 for i in range(self.dialog.results.count())]
        self.assertEqual(len(names), len(set(names)))
        self.assertIn("genshin_amber", names)
        self.assertIn("genshin_fischl", names)
        self.assertIn("genshin_kaveh", names)
        self.assertNotIn("genshin_citlali", names)
        self.assertTrue(self.dialog.communityButton.isEnabled())

    def test_single_and_multiple_explicit_preview_routes(self):
        self.dialog.statusFilter.setCurrentIndex(
            self.dialog.statusFilter.findData("lead"))
        self.dialog.searchBox.setText("genshin_amber")
        self.assertEqual(self.dialog.results.count(), 1)
        with patch("DyberPet.DyberSettings.character_catalog_dialog.QDesktopServices") as desktop:
            self.dialog._open_community_candidate()
            self.assertEqual(desktop.openUrl.call_count, 1)
            self.assertIn("character-amber-ef95b4",
                          desktop.openUrl.call_args.args[0].toString())
        self.dialog.searchBox.setText("genshin_kaveh")
        self.assertEqual(self.dialog.results.count(), 1)
        with patch("DyberPet.DyberSettings.character_catalog_dialog.QInputDialog") as prompt, \
             patch("DyberPet.DyberSettings.character_catalog_dialog.QDesktopServices") as desktop:
            prompt.getItem.return_value = (
                "React-Shimeji Git LFS 来源（动画文件尚待下载）", False)
            self.dialog._open_community_candidate()
            desktop.openUrl.assert_not_called()
            prompt.getItem.return_value = (
                "React-Shimeji Git LFS 来源（动画文件尚待下载）", True)
            self.dialog._open_community_candidate()
            self.assertEqual(desktop.openUrl.call_count, 1)
            self.assertIn("character-kaveh-2f46f2",
                          desktop.openUrl.call_args.args[0].toString())


if __name__ == "__main__":
    unittest.main()

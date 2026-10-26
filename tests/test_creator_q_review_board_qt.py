"""R5 offscreen Qt review board: real PNG previews and no fake endorsements."""
from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PIL import Image

try:
    from PySide6.QtWidgets import QApplication, QInputDialog
    from DyberPet.DyberSettings.creator_q_review_board import (
        CreatorQReviewBoardDialog, review_visible_rows, _valid_creator_link)
except ImportError:
    QApplication = None


@unittest.skipUnless(QApplication is not None, "Qt installed by strict UI jobs only")
class CreatorQBoardQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_filter_18_tile_pagination_and_no_automatic_quality_grade(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            png = root / "creator.png"
            Image.new("RGBA", (24, 68), (151, 71, 94, 255)).save(png)
            rows = [{
                "id": "genshin_amber", "name": "安柏",
                "folder": f"Source{i:02d}", "first_png": str(png),
                "human_q_status": "unreviewed_candidate",
                "risk_priority": 2 if i <= 19 else 0,
                "thin_silhouette_risk": i <= 19,
                "weak_motion_risk": False,
                "source_options": [{"provider": "native", "source_key": "test",
                                    "url": "https://github.com/x/y"}],
            } for i in range(24)]
            board = {"rows": rows, "summary": {
                "installed_artist_variants": 24,
                "thin_risk_versions": 20,
                "weak_motion_versions": 0,
                "personally_q_approved_versions": 0,
            }}
            dialog = CreatorQReviewBoardDialog(root, board=board)
            try:
                self.assertEqual(len(dialog._cards), 18)
                self.assertIn("1 / 2", dialog.page_number.text())
                dialog.next.click()
                self.assertEqual(len(dialog._cards), 2)
                dialog.filter.setCurrentIndex(4)
                self.assertEqual(len(dialog._cards), 0)
                self.assertIn("筛选 0", dialog.page_number.text())
                dialog.filter.setCurrentIndex(5)
                self.assertEqual(len(dialog._cards), 18)
                self.assertIn("本人Q版审核通过 0", dialog.counter.text())
                self.assertTrue(dialog._cards[0].findChildren.__call__)
            finally:
                dialog.close()

    def test_source_url_allowlist_is_not_an_untrusted_redirect(self):
        self.assertTrue(_valid_creator_link("https://github.com/source/creator"))
        self.assertFalse(_valid_creator_link("http://github.com/source/creator"))
        self.assertFalse(_valid_creator_link("https://github.com.bad.site/evil"))
        self.assertFalse(_valid_creator_link("javascript:alert(1)"))
        self.assertFalse(_valid_creator_link("https://evil@github.com/source"))

    def test_source_candidate_click_only_opens_explicitly_selected_url(self):
        with TemporaryDirectory() as folder:
            board = {"rows": [], "summary": {
                "installed_artist_variants": 0,
                "thin_risk_versions": 0,
                "weak_motion_versions": 0,
                "personally_q_approved_versions": 0,
            }}
            dialog = CreatorQReviewBoardDialog(folder, board=board)
            item = {"source_options": [
                {"provider": "native", "source_key": "test",
                 "url": "https://github.com/pinned/art"}]}
            try:
                with patch.object(QInputDialog, "getItem",
                                  return_value=("native: test", False)), \
                     patch("DyberPet.DyberSettings.creator_q_review_board.QDesktopServices.openUrl") as open_url:
                    dialog._open_sources(item)
                    open_url.assert_not_called()
                with patch.object(QInputDialog, "getItem",
                                  return_value=("native: test", True)), \
                     patch("DyberPet.DyberSettings.creator_q_review_board.QDesktopServices.openUrl") as open_url:
                    dialog._open_sources(item)
                    open_url.assert_called_once()
            finally:
                dialog.close()


if __name__ == "__main__":
    unittest.main()

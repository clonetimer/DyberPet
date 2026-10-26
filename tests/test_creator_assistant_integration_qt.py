"""Real Qt button/cancel test for the combined role-gap report."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox
    from DyberPet.DyberSettings.character_catalog_dialog import CharacterCatalogDialog
except ImportError:
    QApplication = None


@unittest.skipIf(QApplication is None, "PySide6 is tested in the Windows Qt job")
class CatalogGapExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_button_requires_user_choice_and_exports_real_json(self):
        row = {"id": "genshin_sayu", "name": "早柚", "family": "genshin",
               "personal_art_structurally_installed": False,
               "native_original_demo": False, "native_preview_ready": False,
               "demo_actions": 0, "demo_frames": 0}
        source = {"characters": [{"id": "genshin_sayu", "source_found": True,
                                  "source_candidate_count": 1,
                                  "style_preference_text": "P1",
                                  "recommended_source": {"preference_order": 1}}]}
        output = {"summary": {"genshin_template_count": 123},
                  "roles": [], "note": "not human approved"}
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "role_gaps.json"
            with patch("DyberPet.DyberSettings.character_catalog_dialog.source_coverage",
                       return_value=source):
                dialog = CharacterCatalogDialog({"characters": [row]}, role_root=td)
            try:
                with patch.object(QFileDialog, "getSaveFileName", return_value=("", "")):
                    dialog.exportGapButton.click()
                self.assertFalse(target.exists())
                with patch.object(QFileDialog, "getSaveFileName",
                                  return_value=(str(target), "JSON 文件 (*.json)")), \
                     patch("tools.creator_assistant_gap_report.make_gap_report",
                           return_value=output) as get_report, \
                     patch.object(QMessageBox, "information") as shown:
                    dialog.exportGapButton.click()
                    self.assertEqual(get_report.call_count, 1)
                    self.assertEqual(Path(get_report.call_args.args[0]), Path(td))
                    self.assertEqual(json.loads(target.read_text(encoding="utf-8")), output)
                    self.assertEqual(shown.call_count, 1)
            finally:
                dialog.close()


if __name__ == "__main__":
    unittest.main()

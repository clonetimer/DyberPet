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



    def test_installed_original_frames_scrub_and_preview_distinguishes_variants(self):
        from DyberPet.DyberSettings.native_frame_preview import (
            NativeFramePreviewDialog, safe_animation_inventory)
        from PIL import Image
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for folder in ("CreatorWave", "CreatorJump"):
                role = root / folder
                (role / "action").mkdir(parents=True)
                act = "wave" if folder == "CreatorWave" else "jump"
                (role / "act_conf.json").write_text(
                    json.dumps({act: {"images": act}}), encoding="utf-8")
                for n in range(3):
                    Image.new("RGBA", (60, 70),
                              (n * 70, 40, 120, 255)).save(
                              role / "action" / f"{act}_{n}.png")
            viewer = NativeFramePreviewDialog(root, ["CreatorWave", "CreatorJump"])
            try:
                self.assertEqual(viewer.action.currentData(), "wave")
                self.assertEqual(viewer.status.text(), "1 / 3")
                viewer._advance()
                self.assertEqual(viewer.status.text(), "2 / 3")
                viewer.version.setCurrentIndex(1)
                self.assertEqual(viewer.action.currentData(), "jump")
                self.assertEqual(viewer.status.text(), "1 / 3")
                viewer.play.click()
                self.assertTrue(viewer._clock.isActive())
                viewer.play.click()
                self.assertFalse(viewer._clock.isActive())
                self.assertEqual(len(safe_animation_inventory(
                    root, "CreatorWave")["wave"]), 3)
            finally:
                viewer.close()

    def test_switching_to_corrupt_original_variant_does_not_crash_ui(self):
        from DyberPet.DyberSettings.native_frame_preview import NativeFramePreviewDialog
        from PIL import Image
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            good = root / "Valid"
            (good / "action").mkdir(parents=True)
            (good / "act_conf.json").write_text(
                json.dumps({"idle": {"images": "idle"}}), encoding="utf-8")
            Image.new("RGBA", (50, 60), (80, 40, 100, 255)).save(
                good / "action" / "idle_0.png")
            (root / "Broken").mkdir()
            viewer = NativeFramePreviewDialog(root, ["Valid", "Broken"])
            try:
                viewer.version.setCurrentIndex(1)
                self.assertIn("版本不可用", viewer.status.text())
                self.assertFalse(viewer.play.isEnabled())
                viewer.version.setCurrentIndex(0)
                self.assertTrue(viewer.play.isEnabled())
                self.assertEqual(viewer.status.text(), "1 / 1")
            finally:
                viewer.close()

    def test_local_visual_review_cannot_claim_approval_without_manual_compare(self):
        from PIL import Image
        from tools.creator_art_manual_review import create_manual_review_receipt
        from DyberPet.DyberSettings.native_frame_preview import NativeFramePreviewDialog
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            folder = root / "Original"
            (folder / "action").mkdir(parents=True)
            (folder / "pet_conf.json").write_text(
                json.dumps({"default": "wave"}), encoding="utf-8")
            (folder / "act_conf.json").write_text(
                json.dumps({"wave": {"images": "wave"}}), encoding="utf-8")
            for idx in range(3):
                Image.new("RGBA", (40, 50), (idx * 60, 120, 90, 255)).save(
                    folder / "action" / f"wave_{idx}.png")
            dlg = NativeFramePreviewDialog(root, ["Original"])
            try:
                dlg.grade.setCurrentIndex(1)
                with self.assertRaisesRegex(ValueError, "对照"):
                    create_manual_review_receipt(
                        root, "Original", dlg._inventory, dlg._visited["Original"],
                        dlg.grade.currentData(), False, False)
                dlg.compared.setChecked(True)
                dlg._advance()
                dlg._advance()
                record = create_manual_review_receipt(
                    root, "Original", dlg._inventory, dlg._visited["Original"],
                    dlg.grade.currentData(), dlg.compared.isChecked(), False)
                self.assertEqual(record["viewer_frame_coverage"],
                                 {"displayed": 3, "total": 3})
                self.assertEqual(record["human_visual_grade"], "A 原设较吻合")
                self.assertFalse(record["official_art_approval"])
                before = record["source_byte_snapshot_sha256"]
                Image.new("RGBA", (40, 50), (2, 2, 2, 255)).save(
                    folder / "action" / "wave_2.png")
                changed = create_manual_review_receipt(
                    root, "Original", dlg._inventory, dlg._visited["Original"],
                    "未评价", False, False)
                self.assertNotEqual(before, changed["source_byte_snapshot_sha256"])
            finally:
                dlg.close()

    def test_demo_role_and_linked_frame_refused_for_visual_quality_review(self):
        from DyberPet.DyberSettings.native_frame_preview import safe_animation_inventory
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            role = root / "Demo"
            role.mkdir()
            (role / "BUILTIN_CHIBI_DEMO.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "演示形象"):
                safe_animation_inventory(root, "Demo")
            with self.assertRaises(ValueError):
                safe_animation_inventory(root, "../outside")

if __name__ == "__main__":
    unittest.main()

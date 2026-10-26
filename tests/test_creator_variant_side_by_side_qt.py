"""R6 Qt tests: original two-variant comparison is always source-bound and read-only."""
from __future__ import annotations
import os
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox
from DyberPet.DyberSettings.creator_variant_side_by_side import (
    CreatorVariantSideBySideDialog, checked_variant_pair,
    shared_native_interactions,
    display_pixmap_for_comparison,
)

def _original(root, folder, profile, colors, *, action_name="left_walk"):
    role = root / folder
    (role / "action").mkdir(parents=True)
    (role / "PERSONAL_IMPORT.json").write_text(
        json.dumps({"selected_profile": profile}), encoding="utf-8")
    (role / "pet_conf.json").write_text(
        json.dumps({"default": "default"}), encoding="utf-8")
    (role / "act_conf.json").write_text(json.dumps({
        "default": {"images": "idle"},
        action_name: {"images": "walk", "need_move": True},
    }), encoding="utf-8")
    Image.new("RGBA",(18,30),(100,180,60,255)).save(
        role / "action" / "idle_0.png")
    for i, rgba in enumerate(colors):
        Image.new("RGBA", (18,30),rgba).save(role/"action"/f"walk_{i}.png")
    return role


class OriginalABTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_reject_same_folder_traversal_and_demo(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "res" / "role"
            _original(root,"SourceAyaka","genshin_ayaka",[(90,40,60,255)])
            _original(root,"SourceCanvasR5Ayaka","genshin_ayaka",[(92,45,65,255)])
            self.assertEqual(checked_variant_pair(root, [
                "SourceAyaka", "SourceCanvasR5Ayaka"]),
                ("SourceAyaka", "SourceCanvasR5Ayaka"))
            with self.assertRaisesRegex(ValueError,"两个不同"):
                checked_variant_pair(root,
                    ["SourceAyaka","SourceCanvasR5Ayaka"],
                    "SourceAyaka","SourceAyaka")
            with self.assertRaisesRegex(ValueError,"Invalid"):
                checked_variant_pair(root,["SourceAyaka","../evil"])
            _original(root,"SourceOther","genshin_venti",[(44,33,22,255)])
            with self.assertRaisesRegex(ValueError,"不同人物"):
                checked_variant_pair(root, ["SourceAyaka", "SourceOther"])
            (root/"SourceAyaka"/"BUILTIN_CHIBI_DEMO.json").write_text("{}")
            with self.assertRaisesRegex(ValueError,"简笔演示"):
                checked_variant_pair(root, ["SourceAyaka","SourceCanvasR5Ayaka"])

    def test_synchronized_cycle_has_different_native_frame_counts(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp)/"res"/"role"
            a=_original(root,"SourceAyaka","genshin_ayaka",
                        [(30,90,70,255),(70,90,30,255)],
                        action_name="left_walk")
            b=_original(root,"SourceCanvasR5Ayaka","genshin_ayaka",
                        [(30,70,90,255),(80,70,80,255),(110,70,100,255)],
                        action_name="walk")
            original_a={p.name:p.read_bytes() for p in (a/"action").glob("*.png")}
            original_b={p.name:p.read_bytes() for p in (b/"action").glob("*.png")}
            ui=CreatorVariantSideBySideDialog(root,[a.name,b.name])
            try:
                self.assertIn("left_walk",ui._inventories[0])
                self.assertIn("walk",ui._inventories[1])
                choices=shared_native_interactions(
                    ui._inventories[0].keys(),ui._inventories[1].keys())
                self.assertEqual([x["category"] for x in choices],["walk"])
                self.assertTrue(ui.apply_shared.isEnabled())
                ui._choose_shared()
                self.assertEqual(len(ui._frames[0]),2)
                self.assertEqual(len(ui._frames[1]),3)
                ui._advance()
                ui._advance()
                self.assertIn("帧 1 / 2",ui.frame_counts[0].text())
                self.assertIn("帧 3 / 3",ui.frame_counts[1].text())
                self.assertEqual(ui._tick,2)
                self.assertNotIn("user_q_standard_eligible",ui.qa[0].text())
                self.assertNotIn("user_q_standard_eligible",ui.qa[1].text())
            finally:
                ui.close()
            self.assertEqual(original_a, {p.name:p.read_bytes() for p in (a/"action").glob("*.png")})
            self.assertEqual(original_b, {p.name:p.read_bytes() for p in (b/"action").glob("*.png")})

    def test_preview_crop_only_removes_transparent_edges_not_author_content(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            path = root / "real_creator.png"
            art = Image.new("RGBA", (40, 90), (0, 0, 0, 0))
            for x in range(10, 25):
                for y in range(15, 65):
                    art.putpixel((x, y), (40, 100, 170, 255))
            art.save(path)
            before = path.read_bytes()
            original = display_pixmap_for_comparison(path, trim_transparent=False)
            tight = display_pixmap_for_comparison(path, trim_transparent=True)
            self.assertEqual((original.width(), original.height()), (40, 90))
            self.assertEqual((tight.width(), tight.height()), (15, 50))
            self.assertEqual(before, path.read_bytes())

    def test_no_cross_variant_action_fabrication_or_auto_action(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp)/"res"/"role"
            _original(root,"SourceVenti","genshin_venti",[(10,20,30,255)],action_name="run")
            _original(root,"SourceCanvasR5Venti","genshin_venti",[(50,60,70,255)],action_name="left_walk")
            ui=CreatorVariantSideBySideDialog(root,["SourceVenti","SourceCanvasR5Venti"])
            try:
                self.assertEqual(ui.shared.count(),0)
                self.assertFalse(ui.apply_shared.isEnabled())
                self.assertEqual(ui._inventories[0].keys(),{"default","run"})
                self.assertEqual(ui._inventories[1].keys(),{"default","left_walk"})
                ui._choose_shared()
                self.assertFalse(ui._clock.isActive())
            finally:
                ui.close()

    def test_native_individual_reviewer_called_for_only_one_selected_folder(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp)/"res"/"role"
            _original(root,"SourceA","genshin_ayaka",[(10,20,30,255)])
            _original(root,"SourceB","genshin_ayaka",[(50,60,70,255)])
            ui=CreatorVariantSideBySideDialog(root,["SourceA","SourceB"])
            try:
                with patch("DyberPet.DyberSettings.native_frame_preview.NativeFramePreviewDialog") as view, \
                     patch.object(QMessageBox, "warning", side_effect=AssertionError("Unexpected blocking Qt warning")), \
                     patch.object(QDialog, "exec", side_effect=AssertionError("Unexpected modal Qt dialog")):
                    instance=view.return_value
                    ui._review(1)
                    view.assert_called_once()
                    self.assertEqual(view.call_args.args[1],["SourceB"])
                    instance.exec.assert_called_once()
            finally:
                ui.close()


if __name__ == "__main__":
    unittest.main()

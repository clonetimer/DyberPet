"""R44: no fake image edits; transparent padding and true pose changes.

Fixtures are ONLY for CI checks, never shipped as fan-character art.
"""
from __future__ import annotations

import hashlib
import os
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from tools.qchibi_pose_geometry import pose_geometry_for_role, sample_frames


def make_png(file, *, width, height, box=None):
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    if box:
        ImageDraw.Draw(img).rectangle(box, fill=(245, 100, 135, 255))
    img.save(file, format="PNG")


class RealPoseGroundingTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root = Path(t.name)

    def test_alpha_geometry_ignores_source_canvas_padding_and_preserves_bytes(self):
        front = self.root / "front.png"
        side = self.root / "side.png"
        make_png(front, width=128, height=128, box=(20, 25, 59, 104))
        make_png(side, width=256, height=256, box=(100, 70, 139, 149))
        unchanged = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                     for p in (front, side)}
        plan = {
            "views": {"front": {"file": front}, "side": {"file": side},
                      "back": {"file": None}},
            "interactions": {"default": {"action": "stand", "frames": [front]}},
            "source_threeview_complete": False,
        }
        result = pose_geometry_for_role(plan)
        self.assertEqual(result["views"]["front"]["visible_height"], 80)
        self.assertEqual(result["views"]["side"]["visible_height"], 80)
        self.assertEqual(result["reference_visible_dimensions"], (40, 80))
        self.assertEqual(result["views"]["front"]["anchor"], (40, 105))
        self.assertEqual(result["views"]["side"]["anchor"], (120, 150))
        self.assertIn("尚无同一造型", " ".join(result["warnings"]))
        self.assertFalse(result["source_art_edited"])
        self.assertFalse(result["visual_quality_approved"])
        self.assertEqual(unchanged, {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                     for p in (front, side)})

    def test_action_union_anchor_does_not_erase_ascending_jump(self):
        frames = []
        for i, bottom in enumerate((90, 70, 45, 70, 90)):
            p = self.root / f"jump_{i}.png"
            make_png(p, width=128, height=128,
                     box=(50, bottom - 20, 67, bottom))
            frames.append(p)
        plan = {
            "views": {"front": {"file": frames[0]},
                      "side": {"file": None}, "back": {"file": None}},
            "interactions": {"default": {"action": "jump", "frames": frames}},
            "source_threeview_complete": False,
        }
        result = pose_geometry_for_role(plan)
        anchor = result["interactions"]["default"]["anchor"]
        self.assertEqual(anchor, (59, 91))
        # Rise/fall intentionally share the same painted pose twice. Their
        # genuine three distinct heights must not be 'invented' as 5 poses.
        self.assertEqual(result["interactions"]["default"]["different_poses"], 3)
        self.assertEqual(result["interactions"]["default"]["bbox_union"], (50, 25, 68, 91))
        self.assertTrue(result["manual_review_required"])

    def test_static_walk_and_reused_left_right_are_flagged(self):
        frame = self.root / "stand.png"
        make_png(frame, width=128, height=128, box=(30, 30, 60, 100))
        plan = {
            "views": {"front": {"file": frame}, "side": {"file": frame},
                      "back": {"file": None}},
            "interactions": {"left": {"action": "walk", "frames": [frame, frame, frame]},
                             "right": {"action": "walk", "frames": [frame, frame, frame]}},
            "source_threeview_complete": False,
        }
        result = pose_geometry_for_role(plan)
        warnings = "；".join(result["warnings"])
        self.assertIn("走路帧没有可见姿态变化", warnings)
        self.assertIn("左右移动引用同一原生动作", warnings)
        self.assertIn("左右移动完全使用相同", warnings)

    def test_blank_and_edge_frames_get_specific_warnings(self):
        blank, touching, safe = [self.root / f"{n}.png"
                                 for n in ("blank", "touching", "safe")]
        make_png(blank, width=100, height=100)
        make_png(touching, width=100, height=100, box=(0, 10, 20, 80))
        make_png(safe, width=100, height=100, box=(10, 15, 30, 85))
        plan = {
            "views": {"front": {"file": safe}, "back": {"file": None}},
            "interactions": {
                "left": {"action": "walk", "frames": [touching, blank, safe]},
            },
            "source_threeview_complete": False,
        }
        result = pose_geometry_for_role(plan)
        self.assertEqual(result["interactions"]["left"]["empty_frames"], 1)
        self.assertEqual(result["interactions"]["left"]["edge_touch_samples"], 1)
        self.assertIn("透明空白", "；".join(result["warnings"]))
        self.assertIn("触及画布边缘", "；".join(result["warnings"]))

    def test_bounded_sample_counts_and_rejects_bogus_frame(self):
        frames = list(range(901))
        result = sample_frames(frames)
        self.assertEqual(len(result), 24)
        self.assertEqual(result[0], 0)
        self.assertEqual(result[-1], 900)
        bad = self.root / "not.png"
        bad.write_bytes(b"bad")
        with self.assertRaisesRegex(ValueError, "PNG"):
            pose_geometry_for_role({
                "views": {"front": {"file": bad}},
                "interactions": {},
                "source_threeview_complete": False,
            })

    def test_qt_r43_native_gallery_uses_common_visible_scale_and_real_action(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        try:
            from PySide6.QtWidgets import QApplication
            from DyberPet.DyberSettings.qchibi_three_view_dialog import QChibiThreeViewDialog
            from tools.generate_mascot_demos import generate_mascot_demos
        except ImportError:
            self.skipTest("Qt not installed")
        folder = self.root / "res" / "role"
        generate_mascot_demos(folder)
        app = QApplication.instance() or QApplication([])
        dialog = QChibiThreeViewDialog(folder / "DemoMascotGuga")
        try:
            self.assertEqual(dialog.plan["pose_geometry"]["source_art_edited"], False)
            self.assertEqual(dialog.plan["pose_geometry"]["visual_quality_approved"], False)
            self.assertTrue(dialog.poseQA.text())
            self.assertFalse(dialog.viewLabels["front"].pixmap().isNull())
            self.assertTrue(dialog.play_interaction("left"))
            dialog.advance_frame()
            self.assertFalse(dialog.animated.pixmap().isNull())
            self.assertIn("向左移动", dialog.actionState.text())
            self.assertTrue(dialog.play_interaction("drag"))
            self.assertTrue(dialog.play_interaction("patpat"))
            self.assertFalse(dialog.animated.pixmap().isNull())
        finally:
            dialog.close()


if __name__ == "__main__":
    unittest.main()

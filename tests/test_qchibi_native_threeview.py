"""R43 Q版三视图一致性与原画交互播放器离线回归。

The fixtures are generated for *tests only*, never distributed as genuine art.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path

from tools.generate_mascot_demos import generate_mascot_demos
from tools.qchibi_native_threeview import native_threeview_interactions


class ThreeViewNativeTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name) / "res" / "role"
        generate_mascot_demos(root)
        self.role = root / "DemoMascotGuga"

    def test_original_motion_bindings_are_real_no_fake_back(self):
        before = {p.relative_to(self.role): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in self.role.rglob("*") if p.is_file()}
        data = native_threeview_interactions(self.role)
        self.assertTrue(data["read_only"])
        self.assertFalse(data["source_threeview_complete"])
        self.assertFalse(data["visual_likeness_verified"])
        self.assertEqual(data["views"]["back"]["file"], None)
        self.assertFalse(data["views"]["side"]["explicit"])
        self.assertIn("未确认", data["views"]["side"]["evidence"])
        self.assertEqual(data["views"]["front"]["file"].name, "idle_0.png")
        self.assertTrue(data["views"]["side"]["file"].name.startswith("left_walk"))
        self.assertEqual(data["interactions"]["left"]["action"], "left_walk")
        self.assertEqual(data["interactions"]["right"]["action"], "right_walk")
        self.assertTrue(data["interactions"]["default"]["frames"][0].is_file())
        after = {p.relative_to(self.role): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in self.role.rglob("*") if p.is_file()}
        self.assertEqual(before, after)

    def _manifest(self, names=("idle_0.png", "left_walk_0.png",
                                "right_walk_1.png")):
        views = {}
        for label, filename in zip(("front", "side", "back"), names):
            file = self.role / "action" / filename
            views[label] = {"file": "action/" + filename,
                            "sha256": hashlib.sha256(file.read_bytes()).hexdigest()}
        return {"schema_version": 1,
                "artist": "test artist same identity",
                "source_url": "https://example.org/one-original-model",
                "variant": "single-2026-costume",
                "views": views}

    def test_three_real_declared_views_from_one_variant_are_displayed(self):
        content = self._manifest()
        (self.role / "Q_CHIBI_3VIEW.json").write_text(
            json.dumps(content), encoding="utf-8")
        data = native_threeview_interactions(self.role)
        self.assertTrue(data["source_threeview_complete"])
        self.assertFalse(data["threeview_human_approved"])
        self.assertTrue(all(data["views"][key]["explicit"] for key in
                            ("front", "side", "back")))
        self.assertIsNotNone(data["views"]["back"]["file"])
        self.assertIn("人工", data["views"]["back"]["evidence"])

    def test_missing_or_forged_threeview_fails_closed(self):
        manifest = self._manifest()
        manifest["views"]["back"]["file"] = "action/../idle_0.png"
        file = self.role / "Q_CHIBI_3VIEW.json"
        file.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Unsafe"):
            native_threeview_interactions(self.role)
        manifest = self._manifest()
        manifest["views"]["back"]["sha256"] = "0" * 64
        file.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "changed"):
            native_threeview_interactions(self.role)
        manifest = self._manifest(names=("idle_0.png", "left_walk_0.png",
                                          "idle_0.png"))
        file.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "same/mirrored"):
            native_threeview_interactions(self.role)

    def test_no_directions_must_not_be_called_strict_threeview(self):
        pet_path = self.role / "pet_conf.json"
        pet = json.loads(pet_path.read_text(encoding="utf-8"))
        pet["left"] = "idle"
        pet["right"] = "idle"
        pet_path.write_text(json.dumps(pet), encoding="utf-8")
        data = native_threeview_interactions(self.role)
        self.assertIsNone(data["views"]["side"]["file"])
        self.assertIsNone(data["views"]["back"]["file"])
        self.assertIn("缺少", data["views"]["side"]["evidence"])

    def test_real_qt_controls_play_actual_frames_and_stop_timer(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        try:
            from PySide6.QtWidgets import QApplication
            from DyberPet.DyberSettings.qchibi_three_view_dialog import QChibiThreeViewDialog
        except ImportError:
            self.skipTest("Qt not installed in this runner")
        app = QApplication.instance() or QApplication([])
        viewer = QChibiThreeViewDialog(self.role)
        try:
            self.assertIn("缺少独立背面原画", viewer.viewLabels["back"].text())
            self.assertFalse(viewer.viewLabels["front"].pixmap().isNull())
            self.assertFalse(viewer.viewLabels["side"].pixmap().isNull())
            self.assertTrue(viewer.actionButtons["left"].isEnabled())
            self.assertTrue(viewer.play_interaction("left"))
            self.assertEqual(viewer.current_action, "left")
            before = viewer.animated.pixmap().toImage()
            viewer.advance_frame()
            self.assertFalse(viewer.animated.pixmap().isNull())
            self.assertGreater(viewer.frame_index, 0)
            self.assertEqual(viewer.animated.pixmap().size().width(), 222)
            self.assertEqual(viewer.animated.pixmap().size().height(), 228)
            self.assertIn("向左移动", viewer.actionState.text())
            self.assertTrue(viewer.play_interaction("right"))
            self.assertEqual(viewer.current_action, "right")
            viewer.toggle()
            self.assertFalse(viewer.timer.isActive())
            viewer.close()
            self.assertFalse(viewer.timer.isActive())
        finally:
            viewer.close()


if __name__ == "__main__":
    unittest.main()

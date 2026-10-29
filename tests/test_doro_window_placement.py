"""R57 Doro: no third-party art, real Qt window lifecycle and screen recovery."""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch
from tools.doro_window_placement import place_doro_window


class DoroPlacementTests(unittest.TestCase):
    def test_fresh_pet_visible_on_primary_screen(self):
        self.assertEqual(
            place_doro_window(None, [(0, 0, 1920, 1080)]),
            (1536, 686, 360, 370))

    def test_saved_position_on_negative_coordinate_second_monitor(self):
        self.assertEqual(
            place_doro_window((-900, 140, 360, 370),
                              [(0, 0, 1920, 1080), (-1920, 0, 1920, 1080)]),
            (-900, 140, 360, 370))

    def test_unplugged_monitor_recovers_into_primary(self):
        x, y, w, h = place_doro_window((-1800, 80, 360, 370),
                                       [(0, 0, 1600, 900)])
        self.assertGreaterEqual(x, 0)
        self.assertGreaterEqual(y, 0)
        self.assertLessEqual(x + w, 1600)
        self.assertLessEqual(y + h, 900)

    def test_bad_settings_and_zero_screen_are_safe(self):
        for value in (None, "broken", ["x", 0, 360, 370],
                      [1, 2, -1, 100], [1, 2], [0, 0, 0, 0]):
            with self.subTest(value=value):
                x, y, w, h = place_doro_window(value, [(0, 0, 1200, 720)])
                self.assertTrue(0 <= x < 1200)
                self.assertTrue(0 <= y < 720)
                self.assertTrue(0 < w <= 1200)
                self.assertTrue(0 < h <= 720)

    def test_saved_position_near_screen_edge_clamped(self):
        x, y, w, h = place_doro_window((1820, 980, 360, 370),
                                       [(0, 0, 1920, 1080)])
        self.assertLessEqual(x + w, 1920)
        self.assertLessEqual(y + h, 1080)

    def test_manual_launch_hides_legacy_only_after_real_load(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        import DyberPet.DyberSettings.doro_live2d_dialog as viewer

        app = QApplication.instance() or QApplication([])
        sentinel = object()
        previous = getattr(app, "p", sentinel)

        class Pet:
            def __init__(self):
                self.visible = True
                self.hides = 0
                self.shows = 0
            def isVisible(self):
                return self.visible
            def hide(self):
                self.hides += 1
                self.visible = False
            def show(self):
                self.shows += 1
                self.visible = True

        class Settings:
            def __init__(self):
                self.data = {}
            def value(self, key, default=None, type=None):
                return self.data.get(key, default)
            def setValue(self, key, value):
                self.data[key] = value

        fake_pet, settings = Pet(), Settings()
        app.p = fake_pet
        info = {"model_json": "synthetic-not-real.model3.json",
                "expressions": [], "motion_groups": {},
                "hit_areas": {}, "extra_motions": {}}
        first = second = None
        try:
            with patch.object(viewer, "QSettings", return_value=settings):
                first = viewer.DoroDesktopWindow(info)
                # Showing before model init does not hide the user's old pet.
                self.assertEqual(fake_pet.hides, 0)
                first.show()
                self.assertEqual(fake_pet.hides, 0)
                # Engine-loaded notification, independent of auto-start flag.
                first._on_model_ready()
                self.assertEqual(fake_pet.hides, 1)
                self.assertFalse(fake_pet.isVisible())
                first.close()
                self.assertEqual(fake_pet.shows, 1)
                self.assertTrue(fake_pet.isVisible())
                # If a model failed before success, original must remain visible.
                second = viewer.DoroDesktopWindow(info)
                second.close()
                self.assertEqual(fake_pet.hides, 1)
                self.assertEqual(fake_pet.shows, 1)
                self.assertIn(viewer._WINDOW_GEOMETRY_KEY, settings.data)
        finally:
            if first:
                first.model = None
                first.close()
            if second:
                second.model = None
                second.close()
            if previous is sentinel:
                del app.p
            else:
                app.p = previous

    def test_reset_to_primary_screen_action_is_available(self):
        from pathlib import Path
        source = (Path(__file__).resolve().parents[1] /
                  "DyberPet" / "DyberSettings" /
                  "doro_live2d_dialog.py").read_text(encoding="utf-8")
        self.assertIn("移回主显示器（恢复位置）", source)
        self.assertIn("self.loadSucceeded.connect(self._on_model_ready)", source)
        self.assertIn("self._restore_window_geometry()", source)
        self.assertNotIn("def showEvent(self, event)", source)


if __name__ == "__main__":
    unittest.main()

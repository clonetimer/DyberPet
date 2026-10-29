"""Tests for Doro-specific source-rig pat and gravity/landing behavior.

No model images or source byte streams are needed. The original Cubism model
is only consulted for parameter IDs/ranges, never modified on disk.
"""
from __future__ import annotations
import math
import unittest
from unittest.mock import patch

from tools.doro_touch_drop import (
    HEAD, BODY, BOUNCE, NativeRange, read_source_ranges, DoroTouchDrop,
)


class SourceTouchDropTests(unittest.TestCase):
    def test_only_existing_model_parameters_are_enabled(self):
        class Rig:
            def GetParamIds(self):
                return [HEAD, BOUNCE, "ParamOther"]
            def GetParamMinById(self, key):
                return -1
            def GetParamMaxById(self, key):
                return 1
            def GetParamDefaultById(self, key):
                return 0
        ranges = read_source_ranges(Rig())
        self.assertEqual(set(ranges), {HEAD, BOUNCE})
        self.assertNotIn(BODY, ranges)

    def test_bad_or_unbounded_model_parameter_is_skipped(self):
        class BadRig:
            def GetParamIds(self):
                return [HEAD, BODY]
            def GetParamMinById(self, key):
                return 5 if key == HEAD else -10
            def GetParamMaxById(self, key):
                return 1 if key == HEAD else 10
            def GetParamDefaultById(self, key):
                return 0
        self.assertEqual(set(read_source_ranges(BadRig())), {BODY})

    def test_head_pat_uses_real_model_angle_and_recovers(self):
        touch = DoroTouchDrop({HEAD: NativeRange(-30, 30, 0)})
        self.assertTrue(touch.pat())
        vals = []
        for _ in range(30):
            touch.tick(.025)
            if HEAD in touch.overrides:
                vals.append(touch.overrides[HEAD])
        self.assertGreater(max(vals), 0)
        self.assertLess(min(vals), 0)
        self.assertFalse(touch.active)
        self.assertEqual(touch.overrides, {})

    def test_missing_head_param_cannot_claim_real_pat_nod(self):
        touch = DoroTouchDrop()
        self.assertFalse(touch.pat())
        touch.tick(.1)
        self.assertEqual(touch.overrides, {})

    def test_fall_reaches_floor_before_bounce_and_stops(self):
        touch = DoroTouchDrop({
            BOUNCE: NativeRange(-1, 1, 0),
            BODY: NativeRange(-15, 15, 0),
        })
        self.assertTrue(touch.drop(150, 550))
        path = []
        touched_body = False
        touched_bounce = False
        for _ in range(80):
            y = touch.tick(.04)
            path.append(y)
            touched_body |= BODY in touch.overrides
            touched_bounce |= BOUNCE in touch.overrides
        self.assertTrue(all(a <= b for a,b in zip(path,path[1:])))
        self.assertAlmostEqual(path[-1], 550)
        self.assertTrue(touched_body)
        self.assertTrue(touched_bounce)
        self.assertFalse(touch.active)
        self.assertEqual(touch.overrides, {})

    def test_drop_without_native_bounce_still_performs_only_physical_motion(self):
        touch = DoroTouchDrop()
        self.assertTrue(touch.drop(50, 250))
        for _ in range(60):
            touch.tick(.04)
            self.assertEqual(touch.overrides, {})
        self.assertEqual(touch.y, 250)

    def test_touch_cancels_fall_and_explicit_landing_cancels_pat(self):
        touch = DoroTouchDrop({HEAD: NativeRange(-30,30,0)})
        touch.drop(100, 700)
        touch.tick(.06)
        self.assertTrue(touch.active)
        touch.pat()
        self.assertEqual(touch.phase, "pat")
        self.assertTrue(touch.drop(100, 500))
        self.assertEqual(touch.phase, "fall")
        touch.cancel()
        self.assertEqual(touch.phase, "idle")

    def test_no_unsafe_runaway_dt_or_negative_floor(self):
        touch = DoroTouchDrop()
        self.assertFalse(touch.drop(float("inf"), 100))
        self.assertTrue(touch.drop(300, 400))
        self.assertAlmostEqual(touch.tick(float("inf")), 300)
        self.assertFalse(touch.active)
        self.assertFalse(touch.drop(100, float("nan")))

    def test_rest_at_floor_is_landing_only(self):
        touch = DoroTouchDrop()
        self.assertFalse(touch.drop(400,400))
        self.assertEqual(touch.phase, "land")
        touch.tick(1)
        self.assertEqual(touch.y,400)

    def test_qt_doro_has_visible_touch_drop_and_render_integration(self):
        import os
        os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
        from PySide6.QtWidgets import QApplication
        from DyberPet.DyberSettings.doro_live2d_dialog import DoroDesktopWindow
        app = QApplication.instance() or QApplication([])
        calls = []
        class FakeRig:
            def GetParamIds(self):
                return [HEAD, BODY, BOUNCE]
            def GetParamMinById(self, k):
                return -1
            def GetParamMaxById(self, k):
                return 1
            def GetParamDefaultById(self, k):
                return 0
            def SetParamById(self, k, val):
                calls.append((k,val))
        info={"model_json": "synthetic.model3.json", "expressions":["Amaze"],
              "motion_groups":{},"hit_areas": {"HitAreaFace":"Face"}}
        window = DoroDesktopWindow(info)
        window.model = FakeRig()
        try:
            with patch("DyberPet.DyberSettings.doro_live2d_dialog.QSettings"):
                window._on_model_ready()
            window._touch_drop.pat()
            window._touch_drop.tick(.06)
            window._after_native_update()
            self.assertTrue(any(k==HEAD for k,v in calls))
            self.assertEqual(window._touch_drop.phase,"pat")
        finally:
            window.model = None
            window.close()

    def test_menu_and_drag_release_implemented_in_qt_source(self):
        from pathlib import Path
        text=(Path(__file__).resolve().parents[1] / "DyberPet" /
              "DyberSettings" / "doro_live2d_dialog.py").read_text("utf-8")
        self.assertIn("self.start_drop(from_drag=True)", text)
        self.assertIn("self._touch_drop.pat()",text)
        self.assertIn("self.express(name, fadeout_ms=700)",text)
        self.assertIn("轻跃下落",text)
        self.assertIn("self._touch_drop.overrides.items()",text)


if __name__ == "__main__":
    unittest.main()

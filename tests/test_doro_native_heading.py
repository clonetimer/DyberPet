"""R67: bounded original Cubism facing cue and continuous Step reversals.

All models here are in-memory SDK mocks; the actual creator artwork is never
copied or inferred to contain missing side/back views.
"""
from __future__ import annotations

import math
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.doro_native_heading import (
    BODY_YAW, HEAD_YAW, NativeDirectionCue, source_direction_cue,
)
from tools.doro_native_gait import NativeStepGait, STEP_ID


class FakeRig:
    def __init__(self, params):
        self.params = params
        self.applied = []
        self.motions = []

    def GetParamIds(self):
        return list(self.params)

    def GetParamMinById(self, key):
        return self.params[key][0]

    def GetParamMaxById(self, key):
        return self.params[key][1]

    def GetParamDefaultById(self, key):
        return self.params[key][2]

    def SetParamById(self, key, value):
        self.applied.append((key, value))

    def StartMotion(self, group, index, priority):
        self.motions.append((group, index, priority))


class DoroDirectionTests(unittest.TestCase):
    def test_prefers_actual_body_over_head_parameter(self):
        rig = FakeRig({
            BODY_YAW: (-15, 15, 0),
            HEAD_YAW: (-30, 30, 0),
            STEP_ID: (-1, 1, 0),
        })
        cue = source_direction_cue(rig)
        self.assertIsNotNone(cue)
        self.assertEqual(cue.param_id, BODY_YAW)
        self.assertEqual(cue.kind, "body")

    def test_fallback_head_yaw_or_no_capability_without_fabricated_view(self):
        self.assertIsNone(source_direction_cue(FakeRig({STEP_ID: (0, 1, 0)})))
        cue = source_direction_cue(FakeRig({HEAD_YAW: (-20, 20, 0)}))
        self.assertEqual(cue.kind, "head")
        self.assertEqual(cue.param_id, HEAD_YAW)

    def test_invalid_source_param_does_not_enable_fake_turn(self):
        for limits in ((10, 0, 3), (-1, 1, 2), (float("nan"), 1, 0)):
            self.assertIsNone(source_direction_cue(FakeRig({BODY_YAW: limits})))
        with self.assertRaises(ValueError):
            NativeDirectionCue("ParamUnrelated", -1, 1, 0)
        self.assertIsNone(source_direction_cue(object()))

    def test_gentle_forward_reverse_has_no_instant_yaw_jump(self):
        cue = NativeDirectionCue(BODY_YAW, -15, 15, 0)
        self.assertTrue(cue.start(1))
        self.assertEqual(cue.override, (BODY_YAW, 0))
        first = []
        for _ in range(6):
            cue.tick(0.04)
            first.append(cue.value)
        self.assertTrue(all(-15 <= v <= 15 for v in first))
        self.assertTrue(all(a <= b for a, b in zip(first, first[1:])))
        last = cue.value
        self.assertTrue(cue.start(-1))
        self.assertEqual(cue.value, last, "reversal must not snap to another view")
        after = []
        for _ in range(8):
            cue.tick(0.04)
            after.append(cue.value)
        self.assertLess(after[-1], 0)
        self.assertTrue(all(-15 <= v <= 15 for v in after))

    def test_releases_to_author_idle_not_endless_override(self):
        cue = NativeDirectionCue(HEAD_YAW, -30, 30, 0)
        cue.start(-1)
        for _ in range(10):
            cue.tick(0.04)
        self.assertIsNotNone(cue.override)
        cue.release()
        for _ in range(25):
            cue.tick(.04)
        self.assertAlmostEqual(cue.value, 0)
        self.assertIsNone(cue.override, "creator's idle owns yaw after recover")
        self.assertEqual(cue.state, "idle")

    def test_nonfinite_dt_fails_closed(self):
        cue = NativeDirectionCue(HEAD_YAW, -30, 30, 0)
        cue.start(1)
        self.assertIsNone(cue.tick(float("inf")))
        self.assertIsNone(cue.override)
        self.assertFalse(cue.start(0))

    def test_native_step_reversal_preserves_phase_amplitude_and_time(self):
        gait = NativeStepGait(-1, 1, 0)
        gait.start(1, 3)
        x = 100.
        for _ in range(11):
            x = gait.tick(.05, x, 0, 700)
        before = (gait.phase, gait.elapsed, gait.value)
        self.assertTrue(gait.start(-1, 3))
        self.assertEqual((gait.phase, gait.elapsed, gait.value), before)
        left = gait.tick(.02, x, 0, 700)
        self.assertLess(left, x)
        self.assertLess(abs(gait.value - before[2]), .5)

    def test_qt_native_draw_uses_actual_yaw_then_releases(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from DyberPet.DyberSettings.doro_live2d_dialog import DoroDesktopWindow

        app = QApplication.instance() or QApplication([])
        info = {
            "model_json": "test-only.model3.json",
            "expressions": [],
            "motion_groups": {"Wave": 1},
            "hit_areas": {}, "extra_motions": {},
        }
        rig = FakeRig({STEP_ID: (-1, 1, 0), BODY_YAW: (-15, 15, 0)})
        win = DoroDesktopWindow(info)
        win.model = rig
        win._available_screens = lambda: [(0, 0, 800, 900)]
        try:
            with patch("DyberPet.DyberSettings.doro_live2d_dialog.QSettings"):
                win._on_model_ready()
            win.move(100, 100)
            self.assertTrue(win.start_walk(1))
            self.assertIsNotNone(win._heading)
            win._heading.tick(.08)
            win._after_native_update()
            self.assertTrue(any(key == BODY_YAW for key, value in rig.applied))
            # Author-authored native motion takes precedence over walking.
            self.assertTrue(win.motion("Wave", 0))
            self.assertFalse(win._gait.active)
            self.assertEqual(rig.motions, [("Wave", 0, 3)])
            for _ in range(25):
                win._heading.tick(.04)
            rig.applied.clear()
            win._after_native_update()
            self.assertFalse(any(key == BODY_YAW for key, value in rig.applied))
        finally:
            win._model_loaded = False
            win.model = None
            win._gait = None
            win._heading = None
            win.close()

    def test_menu_is_explicit_about_front_view_not_side_back_art(self):
        src = (Path(__file__).resolve().parents[1] / "DyberPet" /
               "DyberSettings" / "doro_live2d_dialog.py").read_text("utf-8")
        self.assertIn("原生身体朝向微调（非侧面原画）", src)
        self.assertIn("原生头部朝向微调（非侧面原画）", src)
        self.assertIn("模型未提供原生朝向参数，仍为正面步态", src)
        self.assertNotIn("setTransform(QTransform().scale(-1", src)


if __name__ == "__main__":
    unittest.main()

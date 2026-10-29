"""Doro native Step gait tests: source rig controls, no fabricated frames."""
from __future__ import annotations

import math
import unittest
from unittest.mock import patch

from tools.doro_native_gait import STEP_ID, NativeStepGait, source_step_gait


class NativeStepGaitTests(unittest.TestCase):
    def test_walk_right_advances_native_step_and_window(self):
        gait = NativeStepGait(-1.0, 1.0, 0.0)
        self.assertTrue(gait.start(1, seconds=3))
        x = 200.
        values = []
        for _ in range(20):
            x = gait.tick(.05, x, 0, 700)
            values.append(gait.value)
        self.assertAlmostEqual(x, 272, delta=0.01)
        self.assertTrue(any(v > 0.1 for v in values))
        self.assertTrue(any(v < -0.1 for v in values))
        self.assertTrue(gait.active)

    def test_walk_left_and_stop_restores_model_default(self):
        gait = NativeStepGait(0, 2, 1)
        self.assertTrue(gait.start(-1, 2))
        x = gait.tick(.05, 300, 0, 600)
        self.assertLess(x, 300)
        gait.stop()
        self.assertFalse(gait.active)
        self.assertEqual(gait.value, 1)
        self.assertEqual(gait.tick(.1, x, 0, 600), x)

    def test_only_real_source_param_with_valid_range_can_walk(self):
        class Fake:
            def __init__(self, ids):
                self.ids = ids
            def GetParamIds(self):
                return self.ids
            def GetParamMinById(self, x):
                return -1
            def GetParamMaxById(self, x):
                return 1
            def GetParamDefaultById(self, x):
                return 0
        self.assertIsNone(source_step_gait(Fake(["ParamBreath"])))
        self.assertIsInstance(source_step_gait(Fake([STEP_ID])), NativeStepGait)
        class Broken(Fake):
            def GetParamMaxById(self, x):
                return -1
        self.assertIsNone(source_step_gait(Broken([STEP_ID])))

    def test_boundary_safely_stops_instead_of_walking_offscreen(self):
        gait = NativeStepGait(-1, 1, 0)
        gait.start(1, 4)
        x = gait.tick(.05, 198, 0, 200)
        self.assertEqual(x, 200)
        self.assertFalse(gait.active)
        self.assertEqual(gait.value, 0)

    def test_duration_bound_and_invalid_direction(self):
        gait = NativeStepGait(-1, 1, 0)
        self.assertFalse(gait.start(0))
        self.assertFalse(gait.start(3))
        self.assertFalse(gait.start(1, float("nan")))
        self.assertFalse(gait.active)
        self.assertTrue(gait.start(1, 999))
        self.assertEqual(gait.remaining, 5)
        x = 100.0
        for _ in range(60):
            x = gait.tick(0.1, x, 0, 1000)
        self.assertFalse(gait.active)
        self.assertEqual(gait.value, gait.default)

    def test_nonfinite_inputs_fail_closed(self):
        for values in ((float("nan"), 1, 0), (0, 0, 0), (2, 1, 1),
                       (0, 1, float("inf"))):
            with self.subTest(values=values), self.assertRaises(ValueError):
                NativeStepGait(*values)
        gait = NativeStepGait(-1, 1, 0)
        gait.start(1)
        self.assertEqual(gait.tick(float("inf"), 100, 0, 800), 100)
        self.assertFalse(gait.active)

    def test_native_renderer_step_is_applied_between_update_and_draw(self):
        import os
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from DyberPet.DyberSettings.doro_live2d_dialog import DoroDesktopWindow

        app = QApplication.instance() or QApplication([])
        calls = []
        class FakeModel:
            def GetParamIds(self):
                return [STEP_ID]
            def GetParamMinById(self, id):
                return -1
            def GetParamMaxById(self, id):
                return 1
            def GetParamDefaultById(self, id):
                return 0
            def Update(self):
                calls.append("update")
            def SetParamById(self, id, value):
                calls.append(("step", id, value))
            def Draw(self):
                calls.append("draw")
        info = {"model_json": "synthetic.model3.json",
                "expressions": [], "motion_groups": {},
                "hit_areas": {}, "extra_motions": {}}
        fake = FakeModel()
        window = DoroDesktopWindow(info)
        window.model = fake
        window.live2d = type("FakeLive", (), {"clearBuffer": staticmethod(
            lambda: calls.append("clear"))})()
        try:
            with patch("DyberPet.DyberSettings.doro_live2d_dialog.QSettings"):
                # Bypass user settings in activation; the event is native
                # loadSucceeded, not 'window shown'.
                window._on_model_ready()
            self.assertIsNotNone(window._gait)
            self.assertTrue(window.start_walk(-1))
            window._gait.tick(.05, 200, 0, 500)
            window.paintGL()
            self.assertEqual(calls[0], "clear")
            self.assertEqual(calls[1], "update")
            self.assertEqual(calls[2][0:2], ("step", STEP_ID))
            self.assertEqual(calls[3], "draw")
            window.stop_walk()
            calls.clear()
            window.paintGL()
            self.assertEqual(calls[2], ("step", STEP_ID, 0))
        finally:
            window.model = None
            window._gait = None
            window.close()

    def test_menu_has_native_step_only_if_available(self):
        from pathlib import Path
        src = (Path(__file__).resolve().parents[1] / "DyberPet" /
               "DyberSettings" / "doro_live2d_dialog.py").read_text("utf-8")
        self.assertIn("模型原生 Step", src)
        self.assertIn("当前模型无可用 ParamStep", src)
        self.assertIn("self.model.SetParamById(STEP_ID, self._gait.value)", src)
        self.assertIn("self.stop_walk()", src)


if __name__ == "__main__":
    unittest.main()

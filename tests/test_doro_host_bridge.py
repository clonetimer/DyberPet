"""R61 Doro host integration and smooth source-rig gait (no original art)."""
from __future__ import annotations
import unittest
from tools.doro_host_bridge import DoroHostBridge
from tools.doro_native_gait import NativeStepGait


class Signal:
    def __init__(self):
        self.count = 0
    def emit(self):
        self.count += 1


class DummyValue:
    def __init__(self, val):
        self.val = val
    def value(self):
        return self.val


class DoroHostBridgeTests(unittest.TestCase):
    def test_existing_dashboard_and_control_panel_keep_single_state_owner(self):
        pet = type("Pet", (), {})()
        pet.show_dashboard = Signal()
        pet.show_controlPanel = Signal()
        pet.curr_pet_name = "Kitty"
        pet.pet_hp = DummyValue(82)
        pet.pet_fv = DummyValue(19)
        app = type("App", (), {"p": pet})()
        bridge = DoroHostBridge(app)
        self.assertTrue(bridge.open_dashboard())
        self.assertTrue(bridge.open_control_panel())
        self.assertEqual(pet.show_dashboard.count, 1)
        self.assertEqual(pet.show_controlPanel.count, 1)
        self.assertEqual(bridge.current_host_status(), {
            "base_role": "Kitty", "hp": 82, "fv": 19})
        self.assertEqual(pet.pet_hp.value(), 82)
        self.assertEqual(pet.pet_fv.value(), 19)

    def test_no_main_host_or_deleted_qobject_safely_degrades(self):
        self.assertIsNone(DoroHostBridge(None).current_host_status())
        self.assertFalse(DoroHostBridge(None).open_dashboard())
        pet = type("Pet", (), {"curr_pet_name": "Kitty",
                               "pet_hp": DummyValue(12)})()
        bridge = DoroHostBridge(type("App", (), {"p": pet})())
        self.assertFalse(bridge.open_dashboard())
        self.assertIsNone(bridge.current_host_status())

    def test_doro_menu_exposes_original_host_panels_not_second_database(self):
        from pathlib import Path
        src = (Path(__file__).resolve().parents[1] /
               "DyberPet" / "DyberSettings" /
               "doro_live2d_dialog.py").read_text(encoding="utf-8")
        self.assertIn("DoroHostBridge(QApplication.instance())", src)
        self.assertIn("主程序 · 任务／背包／状态面板", src)
        self.assertIn("主程序 · 角色管理／设置", src)
        self.assertIn("主程序状态（%s）", src)


class SmoothNativeStepTests(unittest.TestCase):
    def test_default_is_respected_even_at_asymmetric_parameter_limit(self):
        gait = NativeStepGait(0, 1, 0)
        self.assertTrue(gait.start(1, seconds=1.0))
        self.assertEqual(gait.value, 0)
        x = 100.0
        samples = []
        for _ in range(20):
            x = gait.tick(.05, x, 0, 500)
            samples.append(gait.value)
        self.assertTrue(all(0 <= v <= 1 for v in samples))
        self.assertLess(samples[0], .1, "step must fade in rather than pop")
        self.assertGreater(max(samples), .4)
        self.assertAlmostEqual(samples[-1], 0, places=8)
        self.assertFalse(gait.active)

    def test_short_walk_still_returns_to_default(self):
        gait = NativeStepGait(-1, 2, 0.4)
        gait.start(-1, .15)
        x = 200.
        for _ in range(4):
            x = gait.tick(.05, x, 0, 500)
        self.assertAlmostEqual(gait.value, .4)
        self.assertFalse(gait.active)

    def test_explicit_stop_and_restart_never_teleport_source_rig(self):
        gait = NativeStepGait(-1, 1, 0.2)
        gait.start(1, 3)
        gait.tick(.06, 200, 0, 400)
        self.assertLess(abs(gait.value - gait.default), .2)
        gait.stop()
        self.assertEqual(gait.value, .2)
        gait.start(-1, 2)
        self.assertEqual(gait.value, .2)
        self.assertAlmostEqual(gait.phase, -1.5707963267948966)


if __name__ == "__main__":
    unittest.main()

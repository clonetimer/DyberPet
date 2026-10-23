"""Motion policies and integration checks for native PetWidget's movement hooks.

The fixtures below use no copyrighted sprite art. The AST harness executes
the actual PetWidget methods against fake geometry, so it checks the wiring
without starting the heavy full desktop application / pynput listener.
"""
import ast
import tempfile
import unittest
from pathlib import Path

from DyberPet.assistant.character_motion import (
    GROUND, DORO, PAIMON, style_for
)


class MotionPolicyTests(unittest.TestCase):
    def test_paimon_hovers_with_bounded_non_drifting_loop(self):
        self.assertEqual(style_for("派蒙"), PAIMON)
        self.assertEqual(style_for("Paimon-Q版"), PAIMON)
        self.assertEqual(PAIMON.ground_lift(), 34)
        samples = [PAIMON.bob_at(t / 20) for t in range(49)]
        self.assertEqual(samples[0], 0)
        self.assertEqual(samples[-1], 0)
        self.assertGreaterEqual(min(samples), -PAIMON.bob_amplitude)
        self.assertLessEqual(max(samples), 0)
        self.assertEqual(PAIMON.bob_at(2.4 * 1000), 0)

    def test_doro_quadruped_requires_existing_native_frames(self):
        self.assertEqual(style_for("Doro"), DORO)
        self.assertEqual(style_for("Dororong"), DORO)
        self.assertEqual(DORO.dx(4.0, on_floor=True, dragging=False), 5.2)
        self.assertEqual(DORO.dx(4, on_floor=False, dragging=False), 4)
        self.assertEqual(DORO.dx(4, on_floor=True, dragging=True), 4)
        self.assertEqual(style_for("Dorothy"), GROUND)

    def test_character_audit_reports_motion_heuristic_without_claiming_gait(self):
        import json
        from DyberPet.assistant.character_fidelity import inspect_character_role
        with tempfile.TemporaryDirectory() as td:
            for name, kind in (("Doro", "quadruped"), ("派蒙", "hover")):
                role = Path(td) / name
                (role / "action").mkdir(parents=True)
                (role / "pet_conf.json").write_text(
                    json.dumps({"width": 64, "height": 64}), encoding="utf-8")
                (role / "act_conf.json").write_text(
                    json.dumps({"default": {"images": "idle"}}), encoding="utf-8")
                result = inspect_character_role(role, name)
                self.assertEqual(result["runtime_motion_policy"]["kind"], kind)
                self.assertEqual(result["authenticity_status"], "not_verified")
                self.assertTrue(any("native" in p or "Paimon" in p or "Doro" in p
                                    for p in result["issues"]))

    def test_other_characters_keep_native_physics(self):
        for character in ("纳西妲", "阿丽莎", "咕嘎", "Kitty", "可莉"):
            with self.subTest(name=character):
                style = style_for(character)
                self.assertEqual(style.kind, "ground")
                self.assertEqual(style.dx(8, on_floor=True, dragging=False), 8)
                self.assertEqual(style.bob_at(1.0), 0)


def extract_pet_methods():
    """Compile precisely the committed PetWidget methods as plain Python."""
    source = Path(__file__).resolve().parents[1] / "DyberPet" / "DyberPet.py"
    code = ast.parse(source.read_text(encoding="utf-8"))
    widget = next(item for item in code.body
                  if isinstance(item, ast.ClassDef) and item.name == "PetWidget")
    names = {"_configure_character_motion", "_hover_motion_tick",
             "_move_customized", "_set_character_motion_enabled"}
    methods = [item for item in widget.body
               if isinstance(item, ast.FunctionDef) and item.name in names]
    if len(methods) != len(names):
        raise AssertionError("Native movement hook missing")
    return compile(ast.Module(body=methods, type_ignores=[]),
                   str(source), "exec")


class MockPos:
    def __init__(self, x, y):
        self._x, self._y = x, y

    def x(self):
        return self._x

    def y(self):
        return self._y

    def topLeft(self):
        return self


class MockTimer:
    def __init__(self):
        self.running = False

    def stop(self):
        self.running = False

    def start(self):
        self.running = True


class MockElapsed:
    def __init__(self):
        self.ms = 0

    def start(self):
        self.ms = 0

    def elapsed(self):
        return self.ms


class Settings:
    tunable_scale = 1.0
    current_anchor = [0, 0]
    draging = 0
    onfloor = 1
    dragspeedx = 0.0
    dragspeedy = 0.0
    SPEED_DECAY = .3
    fall_right = False


class FakePet:
    def __init__(self, name):
        self.curr_pet_name = name
        self._motion_timer = MockTimer()
        self._motion_elapsed = MockElapsed()
        self._hover_offset = 0
        self.floor_pos = 420
        self.is_follow_mouse = False
        self.visible = True
        self._xy = [150, 420]
        self.current_screen = MockPos(0, 0)
        self._screen_max = [1500, 900]
        self._motion_style = GROUND
        self._motion_enabled = True

    def pos(self):
        return MockPos(*self._xy)

    def move(self, x, y):
        self._xy = [int(x), int(y)]

    def height(self):
        return 128

    def isVisible(self):
        return self.visible

    def limit_in_screen(self, x, y, on_action=False):
        return max(0, min(1500, x)), max(0, min(420, y))

    def _configure_character_motion(self):
        return _CALLS["_configure_character_motion"](self)

    def _set_character_motion_enabled(self, enabled):
        return _CALLS["_set_character_motion_enabled"](self, enabled)

    def _hover_motion_tick(self):
        return _CALLS["_hover_motion_tick"](self)

    def _move_customized(self, dx, dy):
        return _CALLS["_move_customized"](self, dx, dy)


_CALLS = {}
_GLOBALS = {
    "style_for": style_for,
    "settings": Settings,
    "GROUND": GROUND,
}
exec(extract_pet_methods(), _GLOBALS, _CALLS)


class ActualNativeHooksTests(unittest.TestCase):
    def setUp(self):
        Settings.onfloor = 1
        Settings.draging = 0
        Settings.current_anchor = [0, 0]
        Settings.tunable_scale = 1.0

    def test_paimon_is_lifted_above_floor_on_activation(self):
        pet = FakePet("派蒙")
        pet._configure_character_motion()
        self.assertTrue(pet._motion_timer.running)
        self.assertEqual(pet.pos().y(), 386)
        self.assertEqual(pet._motion_style.kind, "hover")

    def test_paimon_bob_is_bounded_and_has_no_drift(self):
        pet = FakePet("Paimon")
        pet._configure_character_motion()
        initial_y = pet.pos().y()
        for elapsed in range(0, 2401, 80):
            pet._motion_elapsed.ms = elapsed
            pet._hover_motion_tick()
            self.assertLessEqual(pet.pos().y(), initial_y)
            self.assertGreaterEqual(pet.pos().y(), initial_y - 8)
        pet._motion_elapsed.ms = 2400
        pet._hover_motion_tick()
        self.assertEqual(pet.pos().y(), initial_y)

    def test_drag_and_falling_suspend_hover(self):
        pet = FakePet("派蒙")
        pet._configure_character_motion()
        pet._motion_elapsed.ms = 1200
        pet.is_follow_mouse = True
        pet._hover_motion_tick()
        self.assertEqual(pet.pos().y(), 386)
        pet.is_follow_mouse = False
        Settings.onfloor = 0
        pet._hover_motion_tick()
        self.assertEqual(pet.pos().y(), 386)

    def test_doro_adjusts_horizontal_movement_only_on_floor(self):
        pet = FakePet("Doro")
        pet._configure_character_motion()
        self.assertFalse(pet._motion_timer.running)
        pet._move_customized(10, 0)
        self.assertEqual(pet.pos().x(), 163)
        pet.is_follow_mouse = True
        pet._move_customized(10, 0)
        self.assertEqual(pet.pos().x(), 173)

    def test_gui_motion_opt_out_disables_hover_and_pace(self):
        pet = FakePet("派蒙")
        pet._configure_character_motion()
        self.assertEqual(pet.pos().y(), 386)
        pet._set_character_motion_enabled(False)
        self.assertEqual(pet._motion_style.kind, "ground")
        self.assertEqual(pet.pos().y(), 420)
        self.assertFalse(pet._motion_timer.running)
        pet._set_character_motion_enabled(True)
        self.assertEqual(pet._motion_style.kind, "hover")
        self.assertEqual(pet.pos().y(), 386)
        doro = FakePet("Doro")
        doro._configure_character_motion()
        doro._set_character_motion_enabled(False)
        doro._move_customized(10, 0)
        self.assertEqual(doro.pos().x(), 160)

    def test_original_role_switch_restores_ground(self):
        pet = FakePet("派蒙")
        pet._configure_character_motion()
        pet.curr_pet_name = "Kitty"
        pet._configure_character_motion()
        self.assertEqual(pet._motion_style.kind, "ground")
        self.assertFalse(pet._motion_timer.running)


if __name__ == "__main__":
    unittest.main()

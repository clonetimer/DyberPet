"""Native SubPet Paimon hover regression: pure policy plus real method extraction.

Tests compile SubPet methods from Accessory.py without importing pynput,
qfluentwidgets, desktop Qt or any third-party copyrighted sprite data.
"""
import ast
import unittest
from pathlib import Path

from DyberPet.assistant.character_motion import style_for
from DyberPet.assistant.mini_motion import MiniHover


class MiniHoverPolicyTests(unittest.TestCase):
    def test_only_floor_following_mini_paimon_gets_hover(self):
        args = dict(is_subpet=True, follows_main_y=False, enabled=True)
        self.assertTrue(MiniHover.for_pet("派蒙", **args).enabled)
        self.assertTrue(MiniHover.for_pet("Paimon", **args).enabled)
        for name, changed in (("Doro", args),
                              ("派蒙", {**args, "is_subpet": False}),
                              ("派蒙", {**args, "follows_main_y": True}),
                              ("派蒙", {**args, "enabled": False})):
            with self.subTest(name=name, params=changed):
                self.assertFalse(MiniHover.for_pet(name, **changed).enabled)

    def test_absolute_hover_target_step_limit_and_periodicity(self):
        hover = MiniHover.for_pet("派蒙", is_subpet=True,
                                   follows_main_y=False)
        y = 420
        for _ in range(20):
            next_y = hover.next_y(y, floor_y=420, seconds=0)
            self.assertLessEqual(abs(next_y - y), hover.max_step_px)
            y = next_y
        self.assertEqual(y, 386)
        # Last bob offset always returns to the same absolute baseline.
        for elapsed in range(80, 2401, 80):
            y = hover.next_y(y, floor_y=420, seconds=elapsed / 1000)
        self.assertEqual(y, 386)
        self.assertLessEqual(hover.next_y(y, 420, 1.2), 386)
        self.assertEqual(MiniHover().next_y(77, 420, 1.2), 77)


def extract_subpet_methods():
    source = Path(__file__).resolve().parents[1] / "DyberPet" / "Accessory.py"
    module = ast.parse(source.read_text(encoding="utf-8"))
    cls = next(node for node in module.body
               if isinstance(node, ast.ClassDef) and node.name == "SubPet")
    names = {"_configure_mini_hover", "_tick_mini_hover",
             "toggle_mini_hover", "_closeit", "closeEvent"}
    methods = [node for node in cls.body
               if isinstance(node, ast.FunctionDef) and node.name in names]
    if len(methods) != len(names):
        raise AssertionError("Real SubPet movement methods not found")
    result = {}
    exec(compile(ast.Module(body=methods, type_ignores=[]), str(source), "exec"),
         {"MiniHover": MiniHover, "style_for": style_for}, result)
    return result


ACTUAL = extract_subpet_methods()


class Position:
    def __init__(self, x, y):
        self._x, self._y = x, y

    def x(self):
        return self._x

    def y(self):
        return self._y


class FakeTimer:
    def __init__(self):
        self.running = False
        self.starts = 0

    def start(self):
        self.running = True
        self.starts += 1

    def stop(self):
        self.running = False


class FakeClock:
    def __init__(self):
        self.ms = 0

    def start(self):
        self.ms = 0

    def elapsed(self):
        return self.ms


class FakeAction:
    def __init__(self):
        self.title = None

    def setText(self, title):
        self.title = title


class FakeSignal:
    def __init__(self):
        self.count = 0

    def emit(self, *args):
        self.count += 1


class DummySubPet:
    def __init__(self, name="派蒙", *, follow_main_y=False,
                 is_subpet=True, enabled=True):
        self.pet_name = name
        self.isSubpet = is_subpet
        self.follow_main_y = follow_main_y
        self._mini_hover_enabled = enabled
        self._mini_hover_timer = FakeTimer()
        self._mini_hover_clock = FakeClock()
        self._mini_hover_policy = MiniHover()
        self._xy = [150, 420]
        self.onfloor = 1
        self.draging = 0
        self.is_follow_mouse = False
        self.closing = False
        self.floor_pos = 420
        self.current_anchor = [0, 0]
        self.tunable_scale = 1.0
        self.mini_hover_action = FakeAction()
        self.closed_acc = FakeSignal()
        self.acc_index = "original-mini"
        self.timer = FakeTimer()
        self.closed = False
        self.deleted = False

    def pos(self):
        return Position(*self._xy)

    def move(self, x, y):
        self._xy = [int(x), int(y)]

    def limit_in_screen(self, x, y, on_action=True):
        return max(0, min(600, x)), max(-30, min(420, y))

    def isVisible(self):
        return True

    def _configure_mini_hover(self):
        ACTUAL["_configure_mini_hover"](self)

    def _tick_mini_hover(self):
        ACTUAL["_tick_mini_hover"](self)

    def toggle_mini_hover(self):
        ACTUAL["toggle_mini_hover"](self)

    def close(self):
        self.closed = True

    def deleteLater(self):
        self.deleted = True


class SubPetHookTests(unittest.TestCase):
    def test_floor_follower_gently_rises_without_horizontal_drift(self):
        mini = DummySubPet()
        mini._configure_mini_hover()
        self.assertTrue(mini._mini_hover_timer.running)
        for frame in range(22):
            mini._mini_hover_clock.ms = frame * 80
            mini._tick_mini_hover()
        self.assertEqual(mini.pos().x(), 150)
        self.assertGreaterEqual(mini.pos().y(), 378)
        self.assertLessEqual(mini.pos().y(), 386)

    def test_drag_drop_suspend_hover_without_forcing_teleport(self):
        mini = DummySubPet()
        mini._configure_mini_hover()
        mini.draging = 1
        mini._mini_hover_clock.ms = 1200
        mini._tick_mini_hover()
        self.assertEqual(mini.pos().y(), 420)
        mini.draging = 0
        mini.onfloor = 0
        mini._tick_mini_hover()
        self.assertEqual(mini.pos().y(), 420)
        mini.onfloor = 1
        mini._tick_mini_hover()
        self.assertEqual(mini.pos().y(), 416)

    def test_follow_main_y_is_never_overridden(self):
        mini = DummySubPet(follow_main_y=True)
        mini._configure_mini_hover()
        self.assertFalse(mini._mini_hover_timer.running)
        mini._tick_mini_hover()
        self.assertEqual(mini.pos().y(), 420)

    def test_session_toggle_and_close_stop_timer(self):
        mini = DummySubPet()
        mini._configure_mini_hover()
        mini._mini_hover_clock.ms = 1000
        mini._tick_mini_hover()
        self.assertLess(mini.pos().y(), 420)
        mini.toggle_mini_hover()
        self.assertFalse(mini._mini_hover_timer.running)
        self.assertEqual(mini.pos().y(), 420)
        self.assertEqual(mini.mini_hover_action.title, "Enable Hover")
        mini.toggle_mini_hover()
        self.assertTrue(mini._mini_hover_timer.running)
        self.assertEqual(mini.mini_hover_action.title, "Suspend Hover")
        ACTUAL["_closeit"](mini)
        self.assertFalse(mini._mini_hover_timer.running)
        self.assertTrue(mini.closed)

    def test_close_event_stops_both_original_and_new_timers(self):
        mini = DummySubPet()
        mini._configure_mini_hover()
        mini.timer.start()
        ACTUAL["closeEvent"](mini, object())
        self.assertFalse(mini.timer.running)
        self.assertFalse(mini._mini_hover_timer.running)
        self.assertTrue(mini.deleted)
        self.assertEqual(mini.closed_acc.count, 1)

    def test_no_impact_on_doro_or_other_main_character(self):
        for name, is_subpet in (("Doro", True), ("派蒙", False),
                                ("Kitty", True)):
            mini = DummySubPet(name, is_subpet=is_subpet)
            mini._configure_mini_hover()
            self.assertFalse(mini._mini_hover_timer.running)
            mini._tick_mini_hover()
            self.assertEqual(mini.pos().y(), 420)


if __name__ == "__main__":
    unittest.main()

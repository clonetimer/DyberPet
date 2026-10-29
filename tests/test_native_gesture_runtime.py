"""R45: genuine author gestures run on desktop without sprite replacement.

All fixtures are fake short in-memory actions, NOT third-party artwork.
"""
from __future__ import annotations

import ast
import os
from pathlib import Path
from types import SimpleNamespace
import unittest

from tools.native_gesture_catalog import (
    gesture_frame_index, gesture_timing, native_gesture_catalog,
)


def act(name, *, frames=5, refresh=0.12, repeats=1):
    return SimpleNamespace(images=[name + str(i) for i in range(frames)],
                           frame_refresh=refresh, act_num=repeats, anchor=[0, 0],
                           direction=None, frame_move=0)


def config():
    idle, left, right, pat, wave, skill, unused = (
        act("idle"), act("left"), act("right"), act("pat"),
        act("wave"), act("skill"), act("unused"))
    return SimpleNamespace(
        act_dict={"idle": idle, "left": left, "right": right,
                  "patpat": pat, "wave": wave, "qskill": skill,
                  "cosmetic": unused},
        default=idle, up=idle, down=idle, left=left, right=right,
        drag=pat, fall=pat, prefall=pat, on_floor=idle, focus=idle,
        patpat={0: pat, 1: pat},
        random_act=[[wave]], accessory_act={},
        interact_speed=20,
    )


class NativeGestureTests(unittest.TestCase):
    def test_only_extra_original_loaded_actions_not_pseudo_animation(self):
        catalog = native_gesture_catalog(config())
        self.assertEqual(set(catalog), {"qskill", "cosmetic"})
        self.assertEqual(catalog["qskill"]["frames"], 5)
        self.assertEqual(catalog["qskill"]["ticks"], 30)
        self.assertEqual(catalog["qskill"]["duration_seconds"], 0.6)

    def test_larger_original_refresh_not_multiplied_at_each_20ms_tick(self):
        walk = act("walk", frames=4, refresh=0.12)
        self.assertEqual(gesture_timing(walk, 20)["ticks"], 24)
        sequence = [gesture_frame_index(i, walk, 20) for i in range(24)]
        self.assertEqual(sequence, [0] * 6 + [1] * 6 + [2] * 6 + [3] * 6)
        changed = sum(a != b for a, b in zip(sequence, sequence[1:]))
        self.assertEqual(changed, 3)

    def test_original_repeats_are_kept_and_end_bounded(self):
        gesture = act("shimmer", frames=2, refresh=0.1, repeats=3)
        self.assertEqual(gesture_timing(gesture, 20)["ticks"], 30)
        self.assertEqual(
            [gesture_frame_index(i, gesture, 20) for i in range(0, 30, 5)],
            [0, 1, 0, 1, 0, 1],
        )

    def test_long_invalid_or_placeholder_actions_never_offered(self):
        c = config()
        c.act_dict["infinite"] = act("x", frames=600, refresh=1.0)
        c.act_dict["empty"] = SimpleNamespace(images=[], act_num=1,
                                               frame_refresh=0.1)
        c.act_dict["too_fast"] = act("x", refresh=0.001)
        c.act_dict["unbounded"] = act("x", refresh=float("inf"))
        c.act_dict["suspicious"] = act("x", frames=1300, refresh=0.05)
        c.act_dict["sampled"] = act("sampled", refresh=0.09)
        self.assertEqual(set(native_gesture_catalog(c)),
                         {"qskill", "cosmetic", "sampled"})
        with self.assertRaisesRegex(ValueError, "Invalid"):
            gesture_frame_index(-1, c.act_dict["sampled"], 20)

    def test_actual_right_click_menu_and_worker_are_connected(self):
        root = Path(__file__).resolve().parents[1]
        pet = ast.parse((root / "DyberPet" / "DyberPet.py")
                        .read_text(encoding="utf-8"))
        worker = ast.parse((root / "DyberPet" / "modules.py")
                           .read_text(encoding="utf-8"))
        pet_methods = {n.name: n for n in ast.walk(pet)
                       if isinstance(n, ast.FunctionDef)}
        worker_methods = {n.name: n for n in ast.walk(worker)
                          if isinstance(n, ast.FunctionDef)}
        self.assertIn("_show_native_gesture_picker", pet_methods)
        self.assertIn("native_action", worker_methods)
        menu_src = ast.unparse(pet_methods["_set_menu"])
        picker_src = ast.unparse(pet_methods["_show_native_gesture_picker"])
        worker_src = ast.unparse(worker_methods["native_action"])
        self.assertIn("native_gesture_action", menu_src)
        self.assertIn("self.act_menu.addAction(self.native_gesture_action)", menu_src)
        self.assertIn("start_interact('native_action', choices[selected])", picker_src)
        self.assertIn("self._native_tick = tick + 1", worker_src)
        self.assertIn("self.stop_interact()", worker_src)
        self.assertIn("gesture_frame_index", worker_src)
        self.assertNotIn("save_settings()", picker_src)
        self.assertNotIn("urlopen", worker_src)

    def test_actual_qt_interaction_worker_plays_then_resumes(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        try:
            from PySide6.QtCore import QCoreApplication
            from unittest.mock import patch
            from DyberPet.modules import Interaction_worker
            import DyberPet.settings as settings
        except ImportError:
            self.skipTest("Qt desktop dependencies unavailable")
        app = QCoreApplication.instance() or QCoreApplication([])
        c = config()
        c.act_dict["qskill"] = act("qskill", frames=3, refresh=0.12)
        settings.pet_data = SimpleNamespace(hp_tier=2)
        settings.tunable_scale = 1
        settings.current_img = "initial"
        settings.current_anchor = [0, 0]
        settings.previous_img = "initial"
        settings.previous_anchor = [0, 0]
        settings.playid = 0
        settings.act_id = 0
        settings.current_act = None
        worker = Interaction_worker(c)
        worker.timer.stop()
        changed, moved, finished = [], [], []
        worker.sig_setimg_inter.connect(lambda: changed.append(settings.current_img))
        worker.sig_act_finished.connect(lambda: finished.append(True))
        with patch.object(worker, "_move", side_effect=lambda a: moved.append(a)):
            self.assertTrue(worker.start_interact("native_action", "qskill") is None)
            for i in range(30):
                worker.run()
        self.assertEqual(worker.interact, None)
        self.assertEqual(len(finished), 1)
        self.assertEqual(len(moved), 3)  # source frame changes, not 30 timer ticks
        self.assertTrue(changed)
        self.assertEqual(settings.current_img, "qskill2")
        worker.timer.stop()
        self.assertFalse(worker.start_interact("native_action", "not-an-original"))
        self.assertIsNone(worker.interact)


if __name__ == "__main__":
    unittest.main()

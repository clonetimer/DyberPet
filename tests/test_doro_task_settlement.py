"""R66: task provenance, unique settlement, and edge-safe native walking."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.doro_task_settlement import DoroTaskSettlement
from tools.doro_role_progress import ROLE_KEY, ensure_doro_profile
from tools.doro_vitals import ensure_doro_vitals, record_doro_task, snapshot_doro_vitals


class FakePetData:
    def __init__(self, directory):
        self.frozen_data = False
        self.current_pet = "Kitty"
        self.allData_params = {
            "Kitty": {"HP": 46, "FV": 15, "coins": 27,
                      "items": {"cake": [1, 3]}}
        }
        self.path = Path(directory) / "pet_data.json"
        self.writes = 0

    def save_data(self):
        self.writes += 1
        self.path.write_text(json.dumps(self.allData_params), "utf8")


class DoroTaskSettlementTests(unittest.TestCase):
    def test_focus_start_end_only_once_without_orphan_rewards(self):
        s = DoroTaskSettlement()
        self.assertIsNone(s.transition("focus_end"))
        self.assertIsNone(s.transition("focus_start"))
        self.assertIsNone(s.transition("focus_start"))
        self.assertIsNone(s.transition("focus"))
        self.assertEqual(s.transition("focus_end"), "task_finished")
        self.assertIsNone(s.transition("focus_end"))

    def test_tomato_rest_and_final_completion_are_mutually_exclusive(self):
        s = DoroTaskSettlement()
        results = [s.transition(event) for event in (
            "tomato_start", "tomato", "tomato_rest", "tomato_rest",
            "tomato_start", "tomato", "tomato_end", "tomato_end",
        )]
        self.assertEqual([v for v in results if v],
                         ["pomodoro_finished", "task_finished"])
        self.assertEqual(s.phase, "idle")

    def test_cancel_and_switch_cannot_issue_phantom_credits(self):
        s = DoroTaskSettlement()
        sequence = ("focus_start", "focus_cancel", "focus_end",
                    "tomato_start", "tomato_cencel", "tomato_end",
                    "tomato_rest", "focus_end")
        self.assertFalse(any(s.transition(event) for event in sequence))
        self.assertEqual(s.phase, "idle")

    def test_open_mid_task_requires_new_observed_start(self):
        s = DoroTaskSettlement()
        self.assertIsNone(s.transition("tomato_end"))
        self.assertIsNone(s.transition("focus_end"))
        self.assertIsNone(s.transition("tomato_rest"))
        s.transition("tomato_start")
        s.reset()  # Doro becomes hidden/closed before end
        self.assertIsNone(s.transition("tomato_end"))
        self.assertIsNone(s.transition("focus_end"))

    def test_conflicting_task_modes_cannot_pay_both(self):
        s = DoroTaskSettlement()
        s.transition("focus_start")
        s.transition("tomato_start")
        self.assertIsNone(s.transition("tomato_rest"))
        self.assertEqual(s.transition("focus_end"), "task_finished")
        self.assertIsNone(s.transition("tomato_end"))

    def test_duplicate_host_events_cannot_double_earn_doro_coins(self):
        with tempfile.TemporaryDirectory() as root:
            pet = FakePetData(root)
            ensure_doro_profile(pet)
            ensure_doro_vitals(pet)
            original = json.loads(json.dumps(pet.allData_params["Kitty"]))
            ledger = DoroTaskSettlement()
            before = pet.writes
            events = ("tomato_start", "tomato_rest", "tomato_rest",
                      "tomato_start", "tomato_end", "tomato_end")
            outcomes = []
            for signal in events:
                credit = ledger.transition(signal)
                if credit is not None:
                    self.assertTrue(record_doro_task(pet, credit))
                    outcomes.append(credit)
            self.assertEqual(outcomes, ["pomodoro_finished", "task_finished"])
            status = snapshot_doro_vitals(pet)
            self.assertEqual(status["coins"], 7)
            self.assertEqual(status["tasks"], {
                "task_finished": 1, "pomodoro_finished": 1})
            self.assertEqual(pet.writes, before + 2)
            self.assertEqual(pet.current_pet, "Kitty")
            self.assertEqual(pet.allData_params["Kitty"], original)

    def test_petwidget_keeps_legacy_signals_but_separates_rewards(self):
        source = (Path(__file__).resolve().parents[1] /
                  "DyberPet" / "DyberPet.py").read_text(encoding="utf8")
        self.assertIn('task_phase_changed = Signal(str, name="task_phase_changed")', source)
        self.assertIn("self.task_phase_changed.emit(status)", source)
        self.assertIn("if from_mod == 'Scheduler' and self._doro_live2d_active:", source)
        self.assertIn("sig_addItem_sche.connect(self._add_item_from_scheduler)", source)
        self.assertIn("if not self._doro_live2d_active:", source)
        self.assertIn("self.single_pomo_done.emit()", source)
        self.assertIn("self.taskUI_task_end.emit()", source)

    def test_live2d_uses_canonical_phases_and_unsubscribes_on_close(self):
        source = (Path(__file__).resolve().parents[1] /
                  "DyberPet" / "DyberSettings" /
                  "doro_live2d_dialog.py").read_text("utf8")
        self.assertIn('getattr(pet, "task_phase_changed", None)', source)
        self.assertIn("self._task_settlement.transition(status)", source)
        self.assertIn("self._task_settlement.reset()", source)
        self.assertIn("signal.disconnect(callback)", source)
        self.assertIn("app.p._doro_live2d_active = True", source)
        self.assertIn("app.p._doro_live2d_active = False", source)
        self.assertNotIn('("taskUI_task_end", "task_finished")', source)

    def test_native_walk_at_screen_edge_does_not_spend_energy(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from DyberPet.DyberSettings.doro_live2d_dialog import DoroDesktopWindow
        from tools.doro_native_gait import NativeStepGait

        app = QApplication.instance() or QApplication([])
        win = DoroDesktopWindow({
            "model_json": "synthetic.model3.json", "expressions": [],
            "motion_groups": {}, "hit_areas": {}, "extra_motions": {}
        })
        win._model_loaded = True
        win._gait = NativeStepGait(-1, 1, 0)
        win._available_screens = lambda: [(0, 0, 750, 1000)]
        right = 750 - win.width()
        counts = []
        win._record_doro_action = lambda action: counts.append(action)
        try:
            win.move(right, 100)
            self.assertFalse(win.start_walk(1))
            self.assertEqual(counts, [])
            win.move(0, 100)
            self.assertFalse(win.start_walk(-1))
            self.assertEqual(counts, [])
            win.move(130, 100)
            self.assertTrue(win.start_walk(1))
            self.assertEqual(counts, ["walk_right"])
            win.stop_walk()
        finally:
            win._model_loaded = False
            win._gait = None
            win.model = None
            win.close()


if __name__ == "__main__":
    unittest.main()

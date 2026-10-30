"""R64: real Live2D role vitality and source task signal rewards."""
from __future__ import annotations
import json
import os
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from tools.doro_role_progress import ROLE_KEY, ensure_doro_profile, doro_progress
from tools.doro_vitals import (
    ensure_doro_vitals, record_doro_activity, record_doro_task,
    snapshot_doro_vitals,
)


class PetDataFake:
    def __init__(self, folder):
        self.file_path = str(Path(folder) / "pet_data.json")
        self.current_pet = "Kitty"
        self.frozen_data = False
        self.allData_params = {
            "Kitty": {"HP": 35, "FV": 27, "coins": 10,
                      "items": {"cookie": [1, 2]}}
        }
        self.writes = 0
    def save_data(self):
        self.writes += 1
        Path(self.file_path).write_text(
            json.dumps(self.allData_params), encoding="utf8")


class DoroVitalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.data = PetDataFake(self.temp.name)

    def activate(self):
        ensure_doro_profile(self.data)
        result = ensure_doro_vitals(self.data)
        self.assertIsNotNone(result)
        return result

    def test_migrate_r63_sentinel_and_no_cross_role_changes(self):
        ensure_doro_profile(self.data)
        self.assertEqual(self.data.allData_params[ROLE_KEY]["HP"], -1)
        before = json.loads(json.dumps(self.data.allData_params["Kitty"]))
        state = ensure_doro_vitals(self.data)
        self.assertEqual(state["energy"], 80)
        self.assertEqual(state["bond"], 0)
        self.assertEqual(self.data.current_pet, "Kitty")
        self.assertEqual(self.data.allData_params["Kitty"], before)
        writes = self.data.writes
        ensure_doro_vitals(self.data)
        self.assertEqual(self.data.writes, writes)

    def test_single_write_real_action_updates_energy_bond_and_counts(self):
        self.activate()
        original = self.data.writes
        self.assertTrue(record_doro_activity(self.data, "pat"))
        self.assertEqual(self.data.writes, original + 1)
        self.assertTrue(record_doro_activity(self.data, "walk_left"))
        self.assertTrue(record_doro_activity(self.data, "walk_right"))
        status = snapshot_doro_vitals(self.data)
        self.assertEqual((status["energy"], status["bond"]), (78, 1))
        self.assertEqual(doro_progress(self.data)["pat"], 1)
        self.assertEqual(doro_progress(self.data)["walk_left"], 1)
        self.assertEqual(self.data.allData_params["Kitty"]["FV"], 27)

    def test_true_task_completion_signals_and_reopen_consistency(self):
        self.activate()
        self.assertTrue(record_doro_task(self.data, "pomodoro_finished"))
        self.assertTrue(record_doro_task(self.data, "task_finished"))
        state = snapshot_doro_vitals(self.data)
        self.assertEqual((state["energy"], state["bond"]), (86, 4))
        self.assertEqual(state["tasks"], {"task_finished": 1, "pomodoro_finished": 1})
        restore = PetDataFake(self.temp.name)
        restore.allData_params = json.loads(
            Path(self.data.file_path).read_text("utf8"))
        self.assertEqual(snapshot_doro_vitals(restore), state)
        self.assertEqual(restore.allData_params["Kitty"]["coins"], 10)

    def test_canceled_unknown_and_no_profile_do_not_credit(self):
        self.assertFalse(record_doro_task(self.data, "task_finished"))
        self.assertFalse(record_doro_activity(self.data, "pat"))
        self.assertEqual(self.data.writes, 0)
        self.activate()
        writes = self.data.writes
        for event in ("focus_cancel", "tomato_cencel", "task_start", "garbage"):
            self.assertFalse(record_doro_task(self.data, event))
        self.assertFalse(record_doro_activity(self.data, "unknown"))
        self.assertEqual(self.data.writes, writes)

    def test_stat_boundaries_frozen_save_and_bad_value_repair(self):
        self.activate()
        original = self.data.allData_params[ROLE_KEY]
        original["HP"] = 0
        original["FV"] = 99
        for _ in range(200):
            self.assertTrue(record_doro_activity(self.data, "walk_left"))
        self.assertTrue(record_doro_task(self.data, "task_finished"))
        self.assertEqual(snapshot_doro_vitals(self.data)["energy"], 4)
        self.assertEqual(snapshot_doro_vitals(self.data)["bond"], 100)
        self.data.allData_params[ROLE_KEY]["HP"] = -1
        self.data.allData_params[ROLE_KEY]["FV"] = True
        self.assertEqual(ensure_doro_vitals(self.data)["energy"], 80)
        self.assertEqual(ensure_doro_vitals(self.data)["bond"], 0)
        self.data.frozen_data = True
        before = self.data.writes
        self.assertFalse(record_doro_task(self.data, "pomodoro_finished"))
        self.assertFalse(record_doro_activity(self.data, "pat"))
        self.assertIsNone(ensure_doro_vitals(self.data))
        self.assertEqual(self.data.writes, before)

    def test_snapshot_has_no_live_reference_to_file(self):
        self.activate()
        snap = snapshot_doro_vitals(self.data)
        snap["tasks"]["task_finished"] = 888
        self.assertEqual(snapshot_doro_vitals(self.data)["tasks"]["task_finished"], 0)

    def test_host_bridge_one_role_shared_petdata(self):
        from tools.doro_host_bridge import DoroHostBridge
        import DyberPet.settings as settings
        fake_pet = type("Pet", (), {"curr_pet_name": "Kitty"})()
        app = type("App", (), {"p": fake_pet})()
        with patch.object(settings, "pet_data", self.data, create=True):
            bridge = DoroHostBridge(app)
            bridge.activate_doro_profile()
            self.assertTrue(bridge.record_doro_action("pat"))
            self.assertTrue(bridge.record_completed_task("task_finished"))
            context = bridge.doro_display_context()
            self.assertEqual(context["display_role"], ROLE_KEY)
            self.assertEqual(context["doro_status"]["bond"], 4)
            self.assertEqual(context["doro_status"]["energy"], 84)
            self.assertEqual(self.data.current_pet, "Kitty")

    def test_gui_has_genuine_host_signal_binding_and_disconnection(self):
        s = (Path(__file__).resolve().parents[1] / "DyberPet" /
             "DyberSettings" / "doro_live2d_dialog.py").read_text("utf8")
        self.assertIn('getattr(pet, "task_phase_changed", None)', s)
        self.assertIn('self._task_settlement.transition(status)', s)
        self.assertIn("signal.disconnect(callback)", s)
        self.assertIn("not self._model_loaded or not self.isVisible()", s)
        self.assertIn("Doro 自身 · 活力", s)


if __name__ == "__main__":
    unittest.main()

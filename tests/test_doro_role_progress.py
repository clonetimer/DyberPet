"""R63 Doro per-role interaction persistence in existing PetData save."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from tools.doro_role_progress import (
    ROLE_KEY, ACTIONS, ensure_doro_profile, record_doro_action, doro_progress,
)


class FakePetData:
    def __init__(self, folder):
        self.current_pet = "Kitty"
        self.allData_params = {
            "Kitty": {
                "HP": 77, "FV": 18, "FV_lvl": 1,
                "items": {"cookie": [1, 2]}, "coins": 9,
            }
        }
        self.file_path = str(Path(folder) / "pet_data.json")
        self.frozen_data = False
        self.saves = 0

    def save_data(self):
        self.saves += 1
        with open(self.file_path, "w", encoding="utf-8") as handle:
            json.dump(self.allData_params, handle, ensure_ascii=False)


class DoroRoleProgressTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="doro-progress-r63-")
        self.addCleanup(self.temp.cleanup)
        self.data = FakePetData(self.temp.name)

    def test_real_model_activation_creates_independent_record_in_same_file(self):
        before = json.loads(json.dumps(self.data.allData_params["Kitty"]))
        profile = ensure_doro_profile(self.data)
        self.assertEqual(self.data.current_pet, "Kitty")
        self.assertEqual(self.data.allData_params["Kitty"], before)
        self.assertEqual(profile["doro_interactions"], {a: 0 for a in ACTIONS})
        self.assertEqual(self.data.saves, 1)
        saved = json.loads(Path(self.data.file_path).read_text("utf-8"))
        self.assertIn(ROLE_KEY, saved)
        self.assertIn("Kitty", saved)
        ensure_doro_profile(self.data)
        self.assertEqual(self.data.saves, 1, "no rewrite on repeated GL load")

    def test_real_discrete_actions_record_and_survive_restart(self):
        ensure_doro_profile(self.data)
        for action in ("pat", "walk_left", "walk_right", "drop", "land"):
            self.assertTrue(record_doro_action(self.data, action))
        self.assertTrue(record_doro_action(self.data, "pat"))
        self.assertEqual(doro_progress(self.data)["pat"], 2)
        self.assertEqual(doro_progress(self.data)["land"], 1)
        reloaded = FakePetData(self.temp.name)
        reloaded.allData_params = json.loads(Path(self.data.file_path).read_text("utf-8"))
        self.assertEqual(doro_progress(reloaded)["pat"], 2)
        self.assertEqual(reloaded.current_pet, "Kitty")
        self.assertEqual(reloaded.allData_params["Kitty"]["HP"], 77)
        self.assertEqual(reloaded.allData_params["Kitty"]["FV"], 18)
        self.assertEqual(reloaded.allData_params["Kitty"]["coins"], 9)

    def test_no_model_no_profile_no_writes(self):
        self.assertFalse(record_doro_action(self.data, "pat"))
        self.assertIsNone(doro_progress(self.data))
        self.assertEqual(self.data.saves, 0)

    def test_invalid_action_unknown_prior_record_and_frozen_save_are_safe(self):
        ensure_doro_profile(self.data)
        self.assertFalse(record_doro_action(self.data, "fake_jump"))
        self.assertEqual(self.data.saves, 1)
        self.data.frozen_data = True
        self.assertFalse(record_doro_action(self.data, "pat"))
        self.assertIsNone(ensure_doro_profile(self.data))
        self.assertEqual(self.data.saves, 1)
        self.data.frozen_data = False
        self.data.allData_params[ROLE_KEY] = "other app data"
        self.assertIsNone(ensure_doro_profile(self.data))
        self.assertFalse(record_doro_action(self.data, "pat"))
        self.assertEqual(self.data.allData_params[ROLE_KEY], "other app data")
        self.assertEqual(self.data.saves, 1)

    def test_external_mutation_cannot_corrupt_saved_progress(self):
        profile = ensure_doro_profile(self.data)
        profile["doro_interactions"]["pat"] = 999
        snapshot = doro_progress(self.data)
        snapshot["walk_left"] = 999
        self.assertEqual(doro_progress(self.data)["pat"], 0)
        self.assertEqual(doro_progress(self.data)["walk_left"], 0)

    def test_corrupted_counter_is_repaired_without_overwriting_other_values(self):
        ensure_doro_profile(self.data)
        self.data.allData_params[ROLE_KEY]["doro_interactions"] = {
            "pat": -4, "drop": True, "land": 1.5, "walk_left": 7, "walk_right": 999999999999
        }
        ensure_doro_profile(self.data)
        self.assertEqual(doro_progress(self.data), {
            "pat": 0, "walk_left": 7, "walk_right": 0, "drop": 0, "land": 0
        })

    def test_bridge_uses_real_host_pet_data_singleton(self):
        from tools.doro_host_bridge import DoroHostBridge
        import DyberPet.settings as settings
        fake_pet = type("FakePet", (), {"curr_pet_name": "Kitty"})()
        app = type("App", (), {"p": fake_pet})()
        with patch.object(settings, "pet_data", self.data, create=True):
            bridge = DoroHostBridge(app)
            self.assertIsNotNone(bridge.activate_doro_profile())
            self.assertTrue(bridge.record_doro_action("pat"))
            state = bridge.doro_display_context()
            self.assertEqual(state["display_role"], ROLE_KEY)
            self.assertEqual(state["data_owner"], None)
            self.assertEqual(state["interactions"]["pat"], 1)

    def test_real_live2d_desktop_source_binds_events_only_after_native_load(self):
        source = (Path(__file__).resolve().parents[1] /
                  "DyberPet" / "DyberSettings" / "doro_live2d_dialog.py").read_text("utf-8")
        self.assertIn("self._doro_bridge().activate_doro_profile()", source)
        self.assertIn('self._record_doro_action("walk_left" if direction == -1 else "walk_right")', source)
        self.assertIn('self._record_doro_action("pat")', source)
        self.assertIn('self._record_doro_action("land")', source)
        self.assertIn("Doro Live2D（累计互动 %d 次）", source)


if __name__ == "__main__":
    unittest.main()

"""R65 Doro-only catalog economy, purchase, feed and task settlement regressions."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.doro_role_progress import ROLE_KEY, ensure_doro_profile
from tools.doro_vitals import ensure_doro_vitals, record_doro_task, snapshot_doro_vitals
from tools.doro_feeding import (
    source_food_catalog, doro_inventory, buy_doro_food, feed_doro,
)


class FakePetData:
    def __init__(self, root):
        self.current_pet = "Kitty"
        self.file_path = Path(root) / "pet_data.json"
        self.frozen_data = False
        self.allData_params = {
            "Kitty": {"HP": 39, "FV": 22, "FV_lvl": 1, "coins": 89,
                      "items": {"food": [1, 4]}}
        }
        self.writes = 0

    def save_data(self):
        self.writes += 1
        self.file_path.write_text(json.dumps(self.allData_params), "utf-8")


class FakeItems:
    def __init__(self):
        self.item_dict = {
            "apple": {"item_type": "consumable", "cost": 5,
                      "effect_HP": 13, "effect_FV": 2},
            "sour": {"item_type": "consumable", "cost": 3,
                     "effect_HP": -12, "effect_FV": 1},
            "badge": {"item_type": "accessory", "cost": 2,
                      "effect_HP": 99, "effect_FV": 99},
            "nothing": {"item_type": "consumable", "cost": 1,
                        "effect_HP": 0, "effect_FV": 0},
        }


class DoroFeedingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.pet = FakePetData(self.tmp.name)
        self.items = FakeItems()

    def prepare(self):
        ensure_doro_profile(self.pet)
        ensure_doro_vitals(self.pet)

    def test_earned_coins_buy_and_feed_exactly_one_real_item(self):
        self.prepare()
        sprite = json.dumps(self.pet.allData_params["Kitty"], sort_keys=True)
        self.assertFalse(buy_doro_food(self.pet, self.items, "apple"))
        self.assertTrue(record_doro_task(self.pet, "task_finished"))
        self.assertEqual(snapshot_doro_vitals(self.pet)["coins"], 5)
        count = self.pet.writes
        self.assertTrue(buy_doro_food(self.pet, self.items, "apple"))
        self.assertEqual(self.pet.writes, count + 1)
        self.assertEqual(doro_inventory(self.pet, self.items)["food"][0]["quantity"], 1)
        self.assertEqual(doro_inventory(self.pet, self.items)["coins"], 0)
        self.assertTrue(feed_doro(self.pet, self.items, "apple"))
        self.assertEqual(doro_inventory(self.pet, self.items)["food"], [])
        self.assertEqual(snapshot_doro_vitals(self.pet)["energy"], 97)
        self.assertEqual(snapshot_doro_vitals(self.pet)["bond"], 5)
        self.assertEqual(sprite, json.dumps(self.pet.allData_params["Kitty"], sort_keys=True))
        self.assertEqual(self.pet.current_pet, "Kitty")

    def test_repeated_buy_is_one_stack_and_one_unit_per_feed(self):
        self.prepare()
        for _ in range(4):
            record_doro_task(self.pet, "task_finished")
        self.assertTrue(buy_doro_food(self.pet, self.items, "apple"))
        self.assertTrue(buy_doro_food(self.pet, self.items, "apple"))
        self.assertEqual(doro_inventory(self.pet, self.items)["food"][0]["quantity"], 2)
        self.assertTrue(feed_doro(self.pet, self.items, "apple"))
        self.assertEqual(doro_inventory(self.pet, self.items)["food"][0]["quantity"], 1)

    def test_rejects_nonfood_missing_invalid_or_empty_effect_without_write(self):
        self.prepare()
        record_doro_task(self.pet, "task_finished")
        before = self.pet.writes
        for name in ("badge", "nothing", "not-real-item", None):
            self.assertFalse(buy_doro_food(self.pet, self.items, name))
            self.assertFalse(feed_doro(self.pet, self.items, name))
        self.assertFalse(feed_doro(self.pet, self.items, "apple"))
        self.assertEqual(before, self.pet.writes)
        self.assertEqual(doro_inventory(self.pet, self.items)["coins"], 5)

    def test_cancelled_tasks_do_not_mint_coins(self):
        self.prepare()
        for event in ("tomato_cencel", "focus_cancel", "task_start", "garbage"):
            self.assertFalse(record_doro_task(self.pet, event))
        self.assertEqual(doro_inventory(self.pet, self.items)["coins"], 0)

    def test_restart_persistence_from_same_original_petdata_file(self):
        self.prepare()
        record_doro_task(self.pet, "task_finished")
        buy_doro_food(self.pet, self.items, "apple")
        loaded = FakePetData(self.tmp.name)
        loaded.allData_params = json.loads(self.pet.file_path.read_text("utf-8"))
        self.assertEqual(doro_inventory(loaded, self.items)["food"][0]["quantity"], 1)
        self.assertTrue(feed_doro(loaded, self.items, "apple"))
        self.assertEqual(snapshot_doro_vitals(loaded)["energy"], 97)
        self.assertEqual(loaded.allData_params["Kitty"]["coins"], 89)

    def test_freeze_and_missing_role_do_not_consume_items(self):
        self.assertFalse(buy_doro_food(self.pet, self.items, "apple"))
        self.assertFalse(feed_doro(self.pet, self.items, "apple"))
        self.prepare()
        record_doro_task(self.pet, "task_finished")
        buy_doro_food(self.pet, self.items, "apple")
        before = self.pet.writes
        self.pet.frozen_data = True
        self.assertFalse(feed_doro(self.pet, self.items, "apple"))
        self.assertFalse(buy_doro_food(self.pet, self.items, "apple"))
        self.assertEqual(before, self.pet.writes)

    def test_bad_legacy_inventory_fails_closed_without_overwriting(self):
        self.prepare()
        record_doro_task(self.pet, "task_finished")
        self.pet.allData_params[ROLE_KEY]["items"] = {"apple": ["bad", -2]}
        before = self.pet.writes
        self.assertIsNone(doro_inventory(self.pet, self.items))
        self.assertFalse(buy_doro_food(self.pet, self.items, "apple"))
        self.assertFalse(feed_doro(self.pet, self.items, "apple"))
        self.assertEqual(self.pet.writes, before)
        self.assertEqual(self.pet.allData_params[ROLE_KEY]["items"]["apple"], ["bad", -2])

    def test_source_catalog_is_real_only_with_valid_effects(self):
        names = [f["name"] for f in source_food_catalog(self.items)]
        self.assertEqual(names, ["apple", "sour"])
        self.items.item_dict["bad_float"] = dict(item_type="consumable",
                                                  cost=3.5, effect_HP=5, effect_FV=0)
        self.assertNotIn("bad_float", [f["name"] for f in source_food_catalog(self.items)])

    def test_energy_bond_clamped_for_negative_and_positive_consumables(self):
        self.prepare()
        for _ in range(3):
            record_doro_task(self.pet, "task_finished")
        buy_doro_food(self.pet, self.items, "sour")
        self.assertTrue(feed_doro(self.pet, self.items, "sour"))
        self.assertEqual(snapshot_doro_vitals(self.pet)["energy"], 80)
        self.pet.allData_params[ROLE_KEY]["HP"] = 99
        buy_doro_food(self.pet, self.items, "apple")
        feed_doro(self.pet, self.items, "apple")
        self.assertEqual(snapshot_doro_vitals(self.pet)["energy"], 100)

    def test_bridge_does_not_transfer_original_inventory(self):
        from tools.doro_host_bridge import DoroHostBridge
        import DyberPet.settings as settings
        app = type("App", (), {"p": object()})()
        with patch.object(settings, "pet_data", self.pet, create=True), patch.object(
                settings, "items_data", self.items, create=True):
            bridge = DoroHostBridge(app)
            self.assertIsNotNone(bridge.activate_doro_profile())
            self.assertTrue(bridge.record_completed_task("task_finished"))
            self.assertTrue(bridge.buy_doro_food("apple"))
            self.assertTrue(bridge.feed_doro("apple"))
            self.assertEqual(self.pet.allData_params["Kitty"]["items"]["food"], [1, 4])
            self.assertEqual(self.pet.allData_params["Kitty"]["coins"], 89)

    def test_qt_source_menu_uses_doro_only_bridge(self):
        path = Path(__file__).resolve().parents[1] / "DyberPet" / "DyberSettings" / "doro_live2d_dialog.py"
        s = path.read_text("utf-8")
        self.assertIn("Doro · 购买食物（使用自有金币）", s)
        self.assertIn("Doro · 投喂（只消耗 Doro 库存）", s)
        self.assertIn("self._doro_bridge().feed_doro(name)", s)
        self.assertNotIn("settings.pet_data.change_item(", s)


if __name__ == "__main__":
    unittest.main()

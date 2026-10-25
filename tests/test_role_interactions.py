"""Manual interactions must dispatch only real unlocked actions for current role."""
from __future__ import annotations

import unittest
import tempfile
import json
from pathlib import Path

from tools.character_interaction_coverage import interaction_coverage

from DyberPet.assistant.role_interactions import (
    available_interactions, requested_action, INTERACTION_CATEGORIES)


class RoleInteractionTests(unittest.TestCase):
    def test_unlocked_native_codex_mapping_and_missing_actions(self):
        actions = {"idle", "right_walk", "left_walk", "wave", "jump", "review"}
        result = available_interactions(actions)
        by_id = {x["id"]: x for x in result}
        self.assertEqual(len(result), len(INTERACTION_CATEGORIES))
        self.assertEqual(by_id["greet"]["action"], "wave")
        self.assertEqual(by_id["jump"]["action"], "jump")
        self.assertEqual(by_id["observe"]["action"], "review")
        self.assertEqual(by_id["rest"]["action"], "idle")
        self.assertEqual(by_id["walk"]["action"], "right_walk")
        self.assertFalse(by_id["talk"]["available"])
        self.assertFalse(by_id["sleep"]["available"])
        self.assertIsNone(requested_action(result, "talk"))
        self.assertIsNone(requested_action(result, "hack"))
        self.assertEqual(requested_action(result, "greet"), "wave")

    def test_legacy_chinese_groups_are_exact(self):
        plan = available_interactions(["打招呼", "蹦一蹦", "休息", "左右散步", "说话"])
        self.assertEqual({p["id"] for p in plan if p["available"]},
                         {"greet", "jump", "rest", "walk", "talk"})

    def test_true_shimeji_pat_and_climb_require_original_action_names(self):
        plan = available_interactions(["default", "walk", "patpat", "climb"])
        self.assertEqual(requested_action(plan, "pet"), "patpat")
        self.assertEqual(requested_action(plan, "climb"), "climb")
        self.assertIsNone(requested_action(plan, "greet"))
        self.assertIsNone(requested_action(plan, "sleep"))
        stripped = available_interactions(["default", "walk"])
        self.assertIsNone(requested_action(stripped, "pet"))
        self.assertIsNone(requested_action(stripped, "climb"))

    def test_no_unrelated_or_unlocked_action_is_invented(self):
        for actions in ([], ["attack", "eat", "patpat"], ["wave_effect", "fake_wave"],
                        ["walk_disabled"], [None, 123, "", " jump "]):
            plan = available_interactions(actions)
            self.assertTrue(all(not p["available"] for p in plan))
            self.assertTrue(all(p["action"] is None for p in plan))

    def test_deterministic_without_duplicate_matches(self):
        x = available_interactions(["wave", "hello", "idle", "wave", "left_walk"])
        y = available_interactions(["left_walk", "idle", "hello", "wave"])
        self.assertEqual(x, y)
        self.assertEqual(requested_action(x, "greet"), "wave")


class InteractionCoverageTests(unittest.TestCase):
    def test_only_personal_original_art_counts_not_123_generated_demos(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "DemoSayu").mkdir()
            (root / "CreatorSayu").mkdir()
            (root / "DemoSayu" / "act_conf.json").write_text(
                json.dumps({"wave": {"images": "wave"}}), encoding="utf-8")
            (root / "CreatorSayu" / "act_conf.json").write_text(
                json.dumps({"jump": {"images": "jump"}, "idle": {"images": "idle"}}),
                encoding="utf-8")
            gen = {"characters": [{"profile": "genshin_sayu", "name": "早柚",
                   "installed_folders": [
                       {"folder": "DemoSayu", "is_original_demo": True},
                       {"folder": "CreatorSayu", "is_original_demo": False}]}]}
            masc = {"mascots": [
                {"key": "guga", "display_name": "咕嘎", "imported_creator_art": []},
                {"key": "doro", "display_name": "Doro", "imported_creator_art": []}]}
            result = interaction_coverage(root, genshin_snapshot=gen,
                                          mascot_snapshot=masc)
        self.assertEqual(result["summary"]["template_total"], 3)
        self.assertEqual(result["summary"]["roles_with_creator_art"], 1)
        row = result["characters"][0]
        self.assertEqual(row["actual_action_names"], ["idle", "jump"])
        self.assertIn("jump", row["action_categories_present_in_art"])
        self.assertIn("greet", row["action_categories_missing_in_art"])
        self.assertFalse(row["runtime_unlock_qa_verified"])
        self.assertFalse(row["character_likeness_qa_verified"])
        self.assertFalse(result["characters"][1]["original_creator_art_present"])

    def test_missing_or_unsafe_config_is_reported_not_counted_as_animation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "Broken").mkdir()
            gen = {"characters": [{"profile": "genshin_sayu", "name": "早柚",
                   "installed_folders": [{"folder": "Broken",
                                          "is_original_demo": False}]}]}
            result = interaction_coverage(root, genshin_snapshot=gen,
                                          mascot_snapshot={"mascots": []})
        self.assertEqual(result["summary"]["roles_with_read_errors"], 1)
        self.assertEqual(result["summary"]["roles_with_at_least_one_interaction"], 0)
        self.assertFalse(result["characters"][0]["action_categories_present_in_art"])


if __name__ == "__main__":
    unittest.main()

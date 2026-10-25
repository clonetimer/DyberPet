"""Manual interactions must dispatch only real unlocked actions for current role."""
from __future__ import annotations

import unittest

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


if __name__ == "__main__":
    unittest.main()

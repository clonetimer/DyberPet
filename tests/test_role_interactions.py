"""Manual interactions must dispatch only real unlocked actions for current role."""
from __future__ import annotations

import unittest
import tempfile
import json
import base64
from pathlib import Path

# A tiny real PNG fixture; original identity remains unreviewed.
_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/ScL/nwAAAABJRU5ErkJggg=="
)


def _source_frames(folder, names):
    art = folder / "action"
    art.mkdir(exist_ok=True)
    for name in names:
        (art / (name + "_0.png")).write_bytes(_PNG)


from tools.character_interaction_coverage import interaction_coverage, inspect_selected_role_interactions

from DyberPet.assistant.role_interactions import (
    available_interactions, requested_action, INTERACTION_CATEGORIES,
    choose_random_real_action)


class RoleInteractionTests(unittest.TestCase):
    def test_unlocked_native_codex_mapping_and_missing_actions(self):
        actions = {"idle", "right_walk", "left_walk", "wave", "jump", "review"}
        result = available_interactions(actions)
        by_id = {x["id"]: x for x in result}
        self.assertEqual(len(result), len(INTERACTION_CATEGORIES))
        self.assertEqual(by_id["greet"]["action"], "wave")
        self.assertEqual(by_id["jump"]["action"], "jump")
        self.assertEqual(by_id["observe"]["action"], "review")
        self.assertFalse(by_id["rest"]["available"])  # idle is not a rest animation
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

    def test_climbing_crawling_and_sitting_are_distinct_real_actions(self):
        original = ["default", "idle", "walk", "climb", "crawl", "sit"]
        plan = available_interactions(original)
        self.assertEqual(requested_action(plan, "climb"), "climb")
        self.assertEqual(requested_action(plan, "crawl"), "crawl")
        self.assertEqual(requested_action(plan, "sit"), "sit")
        self.assertIsNone(requested_action(plan, "rest"))  # idle is not a seated/resting animation
        self.assertNotEqual(requested_action(plan, "climb"),
                            requested_action(plan, "crawl"))
        self.assertEqual([x["label"] for x in plan if x["id"] in ("climb", "crawl")],
                         ["攀爬", "匍匐爬行"])
        no_extra_frames = available_interactions(["walk", "idle", "climb"])
        self.assertIsNone(requested_action(no_extra_frames, "crawl"))
        self.assertIsNone(requested_action(no_extra_frames, "sit"))
        no_climb = available_interactions(["crawl", "sit"])
        self.assertIsNone(requested_action(no_climb, "climb"))
        self.assertIsNone(requested_action(no_climb, "rest"))

    def test_random_interaction_never_repeats_when_another_real_action_exists(self):
        plan = available_interactions(["wave", "jump", "idle"])
        self.assertEqual(
            choose_random_real_action(plan, previous="wave", pick=lambda items: items[0]),
            "jump")
        self.assertEqual(
            choose_random_real_action(plan, previous="jump", pick=lambda items: items[0]),
            "wave")
        one = available_interactions(["climb", "idle"])
        self.assertEqual(choose_random_real_action(
            one, previous="climb", pick=lambda items: items[0]), "climb")
        self.assertIsNone(choose_random_real_action(
            available_interactions(["idle", "default"])))
        self.assertIsNone(choose_random_real_action(
            plan, pick=lambda items: "fabricated-action"))
        self.assertIsNone(choose_random_real_action(
            plan, previous="wave", pick=lambda items: "wave"))

    def test_no_unrelated_or_unlocked_action_is_invented(self):
        for actions in ([], ["attack", "eat", "fake_patpat"], ["wave_effect", "fake_wave"],
                        ["walk_disabled"], [None, 123, "", " jump "]):
            plan = available_interactions(actions)
            self.assertTrue(all(not p["available"] for p in plan))
            self.assertTrue(all(p["action"] is None for p in plan))

    def test_run_walk_and_explicit_rest_never_swap_motion_semantics(self):
        actions = available_interactions(["run", "idle", "happy", "climb", "crawl"])
        by_id = {x["id"]: x for x in actions}
        self.assertEqual(by_id["run"]["action"], "run")
        self.assertFalse(by_id["walk"]["available"])
        self.assertFalse(by_id["rest"]["available"])
        self.assertFalse(by_id["jump"]["available"])
        self.assertEqual(by_id["climb"]["action"], "climb")
        self.assertEqual(by_id["crawl"]["action"], "crawl")
        self.assertNotEqual(by_id["climb"]["action"], by_id["crawl"]["action"])
        actions2 = available_interactions(["right_walk", "rest", "sit", "jump"])
        self.assertTrue({k: v["available"] for k, v in
                        ((x["id"], x) for x in actions2)}["sit"])
        self.assertEqual(requested_action(actions2, "walk"), "right_walk")
        self.assertEqual(requested_action(actions2, "rest"), "rest")
        self.assertIsNone(requested_action(actions2, "run"))

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
            _source_frames(root / "CreatorSayu", ("jump", "idle"))
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

class CurrentRoleGapTests(unittest.TestCase):
    def test_current_character_only_reads_install_and_currently_unlocked_actions(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            folder = root / "PersonalKaveh"
            folder.mkdir()
            (folder / "PERSONAL_IMPORT.json").write_text(
                json.dumps({"selected_profile": "genshin_kaveh"}), encoding="utf-8")
            (folder / "act_conf.json").write_text(
                json.dumps({"wave": {"images": "wave"},
                            "jump": {"images": "jump"},
                            "patpat": {"images": "patpat"}}), encoding="utf-8")
            _source_frames(folder, ("wave", "jump", "patpat"))
            report = inspect_selected_role_interactions(
                root, "PersonalKaveh", unlocked_actions=["wave", "madeup"])
            self.assertEqual(report["status"], "imported_artist_claim_not_verified")
            self.assertIn("greet", report["installed_action_categories"])
            self.assertIn("pet", report["installed_action_categories"])
            self.assertEqual(report["currently_unlocked_categories"], ["greet"])
            self.assertIn("sleep", report["missing_categories"])
            self.assertFalse(report["art_likeness_qa_passed"])
            self.assertFalse(report["physical_desktop_qa_passed"])
            (folder / "BUILTIN_CHIBI_DEMO.json").write_text("{}", encoding="utf-8")
            demo = inspect_selected_role_interactions(
                root, "PersonalKaveh", unlocked_actions=["wave"])
            self.assertEqual(demo["status"], "builtin_demo_not_original_art")

    def test_config_only_phantom_actions_never_count_as_available(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            folder = root / "UnfinishedKaveh"
            folder.mkdir()
            (folder / "act_conf.json").write_text(json.dumps({
                "wave": {"images": "wave"},
                "jump": {"images": "jump"},
                "crawl": {"images": "crawl"},
            }), encoding="utf-8")
            _source_frames(folder, ("wave",))
            result = inspect_selected_role_interactions(
                root, folder.name,
                unlocked_actions=["wave", "jump", "crawl"])
            self.assertEqual(result["on_disk_action_names"], ["wave"])
            self.assertEqual(result["configured_but_unplayable_actions"],
                             ["crawl", "jump"])
            self.assertEqual(result["currently_unlocked_categories"], ["greet"])
            self.assertNotIn("jump", result["installed_action_categories"])
            self.assertNotIn("crawl", result["installed_action_categories"])

    def test_absent_or_unsafe_paths_cannot_be_mistaken_for_imported_art(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            empty = inspect_selected_role_interactions(root, "Missing")
            self.assertEqual(empty["status"], "not_installed")
            self.assertFalse(empty["art_likeness_qa_passed"])
            for name in ("..", "../roles", "Foo/Bar", "Foo" + chr(92) + "Bar",
                         "Null" + chr(0), ""):
                with self.assertRaises(ValueError):
                    inspect_selected_role_interactions(root, name)
            (root / "Unknown").mkdir()
            (root / "Unknown" / "act_conf.json").write_text(
                json.dumps({"idle": {}}), encoding="utf-8")
            _source_frames(root / "Unknown", ("idle",))
            unknown = inspect_selected_role_interactions(root, "Unknown")
            self.assertEqual(unknown["status"], "unverified_local_role")
            self.assertFalse(unknown["art_likeness_qa_passed"])



if __name__ == "__main__":
    unittest.main()

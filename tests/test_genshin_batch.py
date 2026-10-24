"""End-to-end catalogue → local intake checks for expanded Genshin roster.

No copyrighted art, voices, remote downloads or implicit reuse permissions.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.genshin_roster import GENSHIN_ROSTER
from tools.genshin_batch import catalogue, plan, seed, select_roles
from tools.chibi_profiles import CHIBI_PROFILES, get_profile, make_bubble_config
from tools.character_pipeline import (PipelineError, record_path,
                                       check_build_gate, load_case)
from tools.audit_character_sources import check_catalog


class GenshinRosterTests(unittest.TestCase):
    def test_twenty_six_distinct_role_templates_in_existing_gui_registry(self):
        self.assertEqual(len(GENSHIN_ROSTER), 26)
        self.assertEqual(len({x["name"] for x in GENSHIN_ROSTER.values()}), 26)
        for key, row in GENSHIN_ROSTER.items():
            with self.subTest(key=key):
                profile_id = "genshin_" + key
                self.assertIn(profile_id, CHIBI_PROFILES)
                profile = get_profile(profile_id)
                self.assertEqual(profile["name"], row["name"])
                self.assertEqual(profile["franchise"], "原神")
                self.assertTrue(100 <= profile["target_height"] <= 130)
                self.assertGreaterEqual(len(row["visual_checks"]), 3)
                self.assertGreaterEqual(len(row["motion_checks"]), 3)
                self.assertFalse(row["original_art_included"])
                self.assertFalse(row["original_voice_included"])
                self.assertEqual(row["asset_rights"], "not_reviewed")
                self.assertFalse(row["publishable"])
                bubble = make_bubble_config(profile_id)
                self.assertEqual(set(bubble), set(row["dialogue"]))
                self.assertTrue(all(item["start_audio"] is None
                                    and item["end_audio"] is None
                                    for item in bubble.values()))

    def test_new_wave_is_distinct_and_unlicensed_by_default(self):
        wave = ("diluc", "jean", "mona", "albedo", "eula", "nilou",
                "alhaitham", "kaveh", "lyney", "lynette", "clorinde",
                "wriothesley")
        for key in wave:
            with self.subTest(key=key):
                role = GENSHIN_ROSTER[key]
                record = catalogue()["genshin_" + key]
                self.assertEqual(record["status"], "research_needed")
                self.assertEqual(record["asset_url"], "")
                self.assertEqual(record["creator"], "")
                self.assertFalse(role["original_art_included"])
                self.assertFalse(role["original_voice_included"])
                self.assertFalse(role["publishable"])
                self.assertEqual(record["kind_suggestion"], "frames")
                self.assertEqual(record["rights_status"], "unknown")

    def test_wanderer_is_floating_and_existing_profiles_remain(self):
        self.assertEqual(get_profile("genshin_wanderer")["ground_mode"], "floating")
        self.assertIn("genshin_paimon", CHIBI_PROFILES)
        self.assertIn("genshin_nahida", CHIBI_PROFILES)
        self.assertIn("genshin_klee", CHIBI_PROFILES)
        self.assertIn("genshin_furina", CHIBI_PROFILES)

    def test_existing_collection_links_are_exact_and_rights_unknown(self):
        catalog = catalogue()
        self.assertEqual(set(catalog), {"genshin_" + key for key in GENSHIN_ROSTER})
        self.assertEqual(check_catalog()["errors"], [])
        for key, row in GENSHIN_ROSTER.items():
            candidate = catalog["genshin_" + key]
            self.assertEqual(candidate["profile"], "genshin_" + key)
            self.assertEqual(candidate["rights_status"], "unknown")
            self.assertEqual(candidate["asset_url"], row["source_work_url"])
            self.assertNotEqual(candidate["status"], "rights_reviewed")
            if key in ("xiao", "wanderer"):
                self.assertTrue(candidate["asset_url"].startswith(
                    "https://www.bilibili.com/video/"))
                self.assertEqual(candidate["channel"], "dyberpet_collection")
            else:
                self.assertEqual(candidate["asset_url"], "")
                self.assertEqual(candidate["status"], "research_needed")

    def test_invalid_ids_and_duplicates_rejected(self):
        for candidate in ("../path", "all,xiao", "hu_tao,hu_tao", "", "unknown"):
            with self.subTest(roles=candidate), self.assertRaises(PipelineError):
                select_roles(candidate)
        self.assertEqual(select_roles("all"), tuple(GENSHIN_ROSTER))
        self.assertEqual(select_roles("xiao,hu_tao"), ("xiao", "hu_tao"))


class GenshinBatchTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name) / "workspace"

    def test_preview_does_not_create_any_files(self):
        preview = seed(self.root, ("xiao", "hu_tao"), dry_run=True)
        self.assertEqual(preview["created"], 0)
        self.assertEqual(preview["mode"], "preview")
        self.assertFalse(self.root.exists())
        self.assertFalse(preview["cases"][0]["needs_source_research"])
        self.assertTrue(preview["cases"][1]["needs_source_research"])
        self.assertFalse(preview["cases"][0]["playable_role_created"])
        self.assertFalse(preview["cases"][0]["publishable"])

    def test_seed_all_creates_isolated_unapproved_cases_and_checklists(self):
        result = seed(self.root, tuple(GENSHIN_ROSTER))
        self.assertEqual(result["created"], 26)
        for row in result["cases"]:
            with self.subTest(id=row["id"]):
                path = record_path(self.root, row["id"])
                case = load_case(path)
                sidecar = self.root / "reviews" / (row["id"] + ".json")
                notes = json.loads(sidecar.read_text(encoding="utf-8"))
                self.assertEqual(case["status"], "discovered")
                self.assertFalse(case["rights"]["local_use"])
                self.assertFalse(case["rights"]["derivative_use"])
                self.assertFalse(case["rights"]["redistribution"])
                self.assertFalse(case["qa"]["visual_pass"])
                self.assertFalse(case["qa"]["runtime_pass"])
                self.assertFalse(notes["visual_pass"])
                self.assertFalse(notes["artwork_available"])
                self.assertEqual(case["profile"], row["profile"])
                self.assertEqual(case["source"]["url"], row["source_url"])
                self.assertEqual(case["source"]["artist"], row["creator"])
                if row["profile"] in ("genshin_xiao", "genshin_wanderer"):
                    self.assertEqual(case["source"]["artist"], "栎咕咕")
                else:
                    self.assertEqual(case["source"]["artist"], "")
                self.assertGreaterEqual(len(notes["human_visual_checks"]), 3)
                with self.assertRaises(PipelineError):
                    check_build_gate(case)

    def test_conflict_does_not_partially_create_batch(self):
        seed(self.root, ("xiao",))
        old = record_path(self.root, "genshin_xiao_main").read_bytes()
        with self.assertRaises(FileExistsError):
            seed(self.root, ("hu_tao", "xiao"))
        self.assertFalse(record_path(self.root, "genshin_hu_tao_main").exists())
        self.assertEqual(old, record_path(self.root, "genshin_xiao_main").read_bytes())

    def test_existing_review_does_not_modify_any_case(self):
        reviews = self.root / "reviews"
        reviews.mkdir(parents=True)
        (reviews / "genshin_zhongli_main.json").write_text("user review")
        with self.assertRaises(FileExistsError):
            seed(self.root, ("hu_tao", "zhongli"))
        self.assertFalse(record_path(self.root, "genshin_hu_tao_main").exists())

    def test_symbolic_candidate_reference_is_rejected(self):
        targets = self.root / "cases"
        targets.mkdir(parents=True)
        candidate = targets / "genshin_hu_tao_main.json"
        try:
            candidate.symlink_to(self.root / "outside_missing.json")
        except (NotImplementedError, OSError):
            self.skipTest("Symlink unavailable on this runner")
        with self.assertRaisesRegex(PipelineError, "symlink"):
            plan(self.root, ("hu_tao",))

    def test_linked_review_workspace_is_rejected_without_writes(self):
        with tempfile.TemporaryDirectory() as outside:
            self.root.mkdir(parents=True)
            review = self.root / "reviews"
            try:
                review.symlink_to(Path(outside), target_is_directory=True)
            except (NotImplementedError, OSError):
                self.skipTest("Directory symlinks unavailable")
            with self.assertRaisesRegex(PipelineError, "Linked"):
                seed(self.root, ("xiao",))
            self.assertFalse(record_path(self.root, "genshin_xiao_main").exists())
            self.assertEqual(list(Path(outside).iterdir()), [])

    def test_cli_lists_and_previews_without_assets(self):
        cli = Path(__file__).resolve().parents[1] / "tools" / "genshin_batch.py"
        for cmd in ("list", "preview"):
            with self.subTest(cmd=cmd):
                args = [sys.executable, str(cli), "--workspace", str(self.root), cmd]
                result = subprocess.run(args, capture_output=True, check=True,
                                        text=True, encoding="utf-8", timeout=25)
                data = json.loads(result.stdout)
                self.assertIn("xiao" if cmd == "list" else "cases", data)
                self.assertFalse(self.root.exists())


if __name__ == "__main__":
    unittest.main()

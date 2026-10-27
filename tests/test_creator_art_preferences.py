"""User preference: detailed original Q chibi first; small real Shimeji accepted.

Tests enforce: pinned provenance != installed art != human visual acceptance.
"""
from __future__ import annotations

import ast
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

from tools.character_source_coverage import source_coverage
from tools.character_catalog_search import query_character_catalog
from tools.creator_art_preference import (
    install_preference, source_style, candidate_character_style)
from tools.character_progress import character_progress


class CreatorArtPreferenceTests(unittest.TestCase):

    def test_source_ledger_utf8_prints_even_when_windows_console_uses_cp1252(self):
        repo = Path(__file__).resolve().parents[1]
        env = dict(os.environ, PYTHONIOENCODING="cp1252")
        result = subprocess.run(
            [sys.executable, str(repo / "tools/character_source_coverage.py")],
            cwd=repo, env=env, capture_output=True, check=True)
        ledger = json.loads(result.stdout.decode("utf-8"))
        self.assertEqual(ledger["summary"]["characters_with_pinned_sources"], 66)
        self.assertTrue(any(x["name"] == "菈乌玛" for x in ledger["characters"]))

    def test_style_labels_are_not_unearned_quality_grades(self):
        self.assertEqual(install_preference("artist_genshin"), 0)
        self.assertEqual(install_preference("artist_codex"), 1)
        self.assertEqual(install_preference("artist_external_codex"), 1)
        self.assertEqual(install_preference("pinned_codexpetdb"), 1)
        self.assertEqual(install_preference("artist_shimeji"), 2)
        self.assertEqual(install_preference("artist_nano"), 2)
        self.assertEqual(install_preference("pinned_eula_shimeji"), 2)
        for kind in ("native", "codex", "independent_codex", "codexpetdb_zip", "react_lfs", "shimeji", "nano_shimeji", "pinned_eula_creator"):
            result = source_style(kind)
            self.assertIsNone(result["visual_grade"])
            self.assertEqual(result["visual_qa_status"], "pending_human_review")
        with self.assertRaises(ValueError):
            install_preference("generated_placeholder")
        with self.assertRaises(ValueError):
            source_style("wrong_character")

    def test_61_creator_sources_and_62_honest_gaps(self):
        result = source_coverage()
        summary = result["summary"]
        self.assertEqual(summary["template_count"], 123)
        self.assertEqual(summary["characters_with_pinned_sources"], 66)
        self.assertEqual(summary["characters_without_pinned_sources"], 57)
        self.assertEqual(summary["pinned_source_options"], 89)
        self.assertEqual(summary["style_priority_detailed_native_count"], 3)
        self.assertEqual(summary["user_visible_style_grades_approved"], 0)
        total = sum(summary[x] for x in (
            "style_priority_detailed_native_count",
            "style_priority_atlas_pending_count",
            "style_priority_shimeji_candidate_count"))
        self.assertEqual(total, 66)
        refs = {row["id"]: row for row in result["characters"]}
        for key in ("genshin_nahida", "genshin_xiao", "genshin_wanderer"):
            self.assertEqual(refs[key]["recommended_source"]["provider"], "native")
            self.assertEqual(refs[key]["style_preference_group"], "detailed_candidate")
        for key in ("genshin_traveler_aether", "genshin_traveler_lumine", "genshin_zhongli"):
            self.assertEqual(refs[key]["style_preference_group"], "small_candidate")
        self.assertEqual(refs["genshin_keqing"]["source_candidate_count"], 2)
        self.assertEqual(refs["genshin_lisa"]["source_candidate_count"], 0)
        self.assertEqual(refs["genshin_sayu"]["source_candidate_count"], 1)
        self.assertIsNone(refs["genshin_lisa"]["recommended_source"])
        for row in result["characters"]:
            self.assertIsNone(row["visual_grade"])
            self.assertFalse(row["visual_likeness_qa_passed"])
            for candidate in row["source_candidates"]:
                self.assertIsNone(candidate["visual_grade"])
                self.assertTrue(candidate["needs_manual_likeness_and_rights_review"])
                self.assertFalse(candidate["asset_is_bundled"])
            ordered = [c["preference_order"] for c in row["source_candidates"]]
            self.assertEqual(ordered, sorted(ordered))

    def test_first_launch_shows_source_candidates_without_fake_install(self):
        result = source_coverage()
        lookup = {item["id"]: item for item in result["characters"]}
        progress = character_progress(Path("/not/a/created/role/folder"))["characters"]
        visible = query_character_catalog(progress, family="genshin",
                                          status="source", source_lookup=lookup)
        missing = query_character_catalog(progress, family="genshin",
                                          status="source_missing", source_lookup=lookup)
        self.assertEqual(len(visible), 66)
        self.assertEqual(len(missing), 57)
        self.assertEqual(len(query_character_catalog(progress, family="genshin")), 123)
        self.assertEqual(query_character_catalog(progress, status="personal"), [])
        self.assertEqual(visible[0]["id"] in ("genshin_nahida", "genshin_xiao", "genshin_wanderer"), True)
        self.assertFalse(any(row["personal_art_structurally_installed"] for row in visible))
        with self.assertRaises(ValueError):
            query_character_catalog(progress, status="source")
        with self.assertRaises(ValueError):
            query_character_catalog(progress, status="source_missing")

    def test_gui_uses_explicit_preference_for_picker_and_catalog(self):
        base = Path(__file__).resolve().parents[1]
        c=(base/"DyberPet/DyberSettings/CharCardUI.py").read_text("utf-8")
        d=(base/"DyberPet/DyberSettings/character_catalog_dialog.py").read_text("utf-8")
        ast.parse(c)
        ast.parse(d)
        self.assertIn("sorted(labels, key=lambda name: (install_preference(", c)
        self.assertIn('("有公开作者素材可获取（未必已安装）", "source")', d)
        self.assertIn('("仍缺公开作者素材（待补齐）", "source_missing")', d)
        self.assertIn("source_lookup=self._source_by_id", d)
        self.assertIn("① 精细Q版优先", c)
        self.assertIn("③ 可接受小型 Shimeji", c)
        # A fixed-source character must be selectable *from that character's
        # own "install artist art" action, not only the generic Add menu.
        self.assertIn('from tools.install_pinned_codexpetdb import listed_packages, fixed_archive_url', c)
        self.assertIn('for key, row in petdb.items()', c)
        self.assertIn('("pinned_codexpetdb", key)', c)
        self.assertIn('if mode == "pinned_codexpetdb":', c)
        self.assertIn('return petdb[key]["profile"]', c)
        self.assertIn('source = fixed_archive_url(petdb[kind])', c)
        # Verified Amber and Fischl were previously source_found but missing
        # from the per-character install menu. This must not regress.
        self.assertIn('verified_react = verified_lfs_sources()', c)
        self.assertIn('for profile, row in verified_react.items()', c)
        self.assertIn('("react_shimeji_lfs", profile)', c)
        self.assertIn('if mode == "react_shimeji_lfs":', c)
        self.assertIn('mode="react_shimeji_lfs", profile=kind, preset=None', c)
        from tools.react_shimeji_source_leads import verified_lfs_sources
        self.assertEqual(set(verified_lfs_sources()), {
            "genshin_amber", "genshin_fischl"
        })
        self.assertEqual(install_preference("react_shimeji_lfs"), 1)
        # The accepted creator modes are a semantic set, not a brittle
        # single-line string. Local ZIP imports must get the same real-frame
        # review prompt as network-pinned original artwork.
        import_tree = ast.parse(c)
        method = next(x for cls in import_tree.body if isinstance(cls, ast.ClassDef)
                      for x in cls.body if isinstance(x, ast.FunctionDef)
                      and x.name == "_onChibiImportComplete")
        values = [ast.literal_eval(n.value) for n in ast.walk(method)
                  if isinstance(n, ast.Assign) and any(
                      isinstance(t, ast.Name) and t.id == "original_modes"
                      for t in n.targets)]
        self.assertEqual(len(values), 1)
        self.assertTrue({"pinned_codexpetdb", "pinned_codexpetdb_local",
                         "react_shimeji_lfs", "creator_source",
                         "shimeji_zip", "codex_zip"}.issubset(values[0]))
        from tools.install_pinned_codexpetdb import listed_packages, fixed_archive_url
        packages = listed_packages()["sources"]
        self.assertEqual({v["profile"] for v in packages.values()}, {
            "genshin_kaveh", "genshin_kinich", "genshin_kirara",
            "genshin_alhaitham", "genshin_baizhu", "genshin_candace",
            "genshin_chevreuse", "genshin_layla", "genshin_chiori",
            "genshin_charlotte", "genshin_columbina", "genshin_gaming",
            "genshin_iansan",
            "genshin_cyno", "genshin_dehya", "genshin_freminet",
            "genshin_aino", "genshin_dahlia", "genshin_flins", "genshin_lan_yan",
            "genshin_durin", "genshin_ineffa", "genshin_jahoda", "genshin_lauma",
            "genshin_alyosha", "genshin_lohen", "genshin_odette", "genshin_prune",
            "genshin_yanfei", "genshin_emilie", "genshin_illuga", "genshin_zibai"
        })
        self.assertEqual(len({fixed_archive_url(v) for v in packages.values()}), 32)


if __name__ == "__main__":
    unittest.main()

"""R29: Keqing's original 92 PNGs are ANOTHER author version, not persona 70."""
from __future__ import annotations
import ast
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tools.character_source_coverage import source_coverage
from tools.personal_source_batch import plan_personal_sources, INSTALLERS
from tools.creator_art_preference import install_preference


class KeqingR29Registry(unittest.TestCase):
    def test_source_coverage_persona_count_not_inflated(self):
        report=source_coverage()
        s=report["summary"]
        self.assertEqual(s["template_count"],123)
        self.assertEqual(s["characters_with_pinned_sources"],69)
        self.assertEqual(s["characters_without_pinned_sources"],54)
        self.assertEqual(s["pinned_source_options"],93)
        keqing=next(x for x in report["characters"] if x["id"]=="genshin_keqing")
        self.assertEqual(keqing["name"],"刻晴")
        self.assertFalse(keqing["installed"])
        sources=[x for x in keqing["source_candidates"] if x["provider"]=="gmcy_keqing"]
        self.assertEqual(len(sources),1)
        source=sources[0]
        self.assertEqual(source["source_key"],"keqing_92")
        self.assertEqual(source["verified_original_git_blob_count"],92)
        self.assertEqual(source["original_creator_action_groups"],6)
        self.assertFalse(source["source_author_likeness_qa_passed"])
        self.assertFalse(source["prebundled_original_art"])

    def test_opt_in_plan_has_exact_pinned_keqing_variant(self):
        self.assertEqual(install_preference("gmcy_keqing_original"),1)
        self.assertIn("gmcy_keqing",INSTALLERS)
        with TemporaryDirectory() as t:
            plan=plan_personal_sources(Path(t)/"fresh")
        self.assertEqual(plan["summary"]["ready_for_opt_in"],69)
        self.assertEqual(plan["summary"]["missing_source"],54)
        row=next(x for x in plan["characters"] if x["profile"]=="genshin_keqing")
        self.assertTrue(any(x["provider"]=="gmcy_keqing" and x["source_key"]=="keqing_92"
                            for x in row["supported_sources"]))
        self.assertFalse(row["original_likeness_verified"])

    def test_real_character_ui_has_safe_keqing_selection(self):
        s=(Path(__file__).resolve().parents[1]/"DyberPet/DyberSettings/CharCardUI.py").read_text("utf-8")
        ast.parse(s)
        self.assertIn('mode="gmcy_keqing_original"',s)
        self.assertIn('elif self.mode == "gmcy_keqing_original":',s)
        self.assertIn('if mode == "gmcy_keqing_original":',s)
        self.assertIn('return "genshin_keqing"',s)
        self.assertIn('install_gmcy_keqing(',s)
        self.assertIn("不覆盖当前安装的其他刻晴版本",s)


if __name__=="__main__":
    unittest.main()

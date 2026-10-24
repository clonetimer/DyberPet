"""Cross-family completion must be grounded in actual installed animation."""
from __future__ import annotations

import ast
import json
import tempfile
import unittest
from pathlib import Path

from tools.character_progress import character_progress
from tools.generate_builtin_chibi_demos import generate_demo_roles
from tools.generate_mascot_demos import generate_mascot_demos


class CharacterCoverageTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)/"res"/"role"

    def test_empty_repo_has_all_templates_but_zero_actual_animations(self):
        info=character_progress(self.root)
        s=info["summary"]
        self.assertEqual(s["template_total"],125)
        self.assertEqual(s["genshin_templates"],123)
        self.assertEqual(s["mascot_templates"],2)
        self.assertEqual(s["original_demo_ready"],0)
        self.assertEqual(s["native_preview_ready"],0)
        self.assertEqual(s["missing_native_animation"],125)
        self.assertFalse(self.root.exists())
        self.assertTrue(all(not x["creator_art_and_likeness_verified"]
                            and not x["character_voice_verified"]
                            and not x["physical_desktop_qa_verified"]
                            for x in info["characters"]))

    def test_local_sample_equal_native_actions_distinct_character_bodies(self):
        generate_demo_roles(self.root,["genshin_lisa","genshin_xiao"])
        generate_mascot_demos(self.root)
        before={x.relative_to(self.root):x.read_bytes() for x in self.root.rglob("*")
                if x.is_file()}
        result=character_progress(self.root)
        after={x.relative_to(self.root):x.read_bytes() for x in self.root.rglob("*")
               if x.is_file()}
        self.assertEqual(before,after)
        s=result["summary"]
        self.assertEqual(s["original_demo_ready"],4)
        self.assertEqual(s["native_preview_ready"],4)
        self.assertEqual(s["missing_native_animation"],121)
        self.assertEqual(s["personal_art_structurally_installed"],0)
        self.assertEqual(s["genshin_demo_actions"],[10])
        self.assertEqual(s["mascot_demo_actions"],[10])
        rows={v["id"]:v for v in result["characters"]}
        self.assertEqual(rows["genshin_lisa"]["demo_frames"],66)
        self.assertEqual(rows["mascot_doro"]["demo_frames"],66)
        self.assertEqual(rows["mascot_guga"]["demo_actions"],10)
        self.assertFalse(any(v["creator_art_and_likeness_verified"]
                             for v in result["characters"]))
        self.assertNotIn(str(self.root),json.dumps(result,ensure_ascii=False))

    def test_guids_use_shared_qt_viewer_and_real_existing_switch_signal(self):
        p=Path(__file__).resolve().parents[1]/"DyberPet"/"DyberSettings"/"CharCardUI.py"
        tree=ast.parse(p.read_text(encoding="utf-8"))
        methods={n.name:ast.unparse(n) for n in ast.walk(tree)
                 if isinstance(n,ast.FunctionDef)}
        self.assertIn("_openGenshinRoleActions",methods)
        self.assertIn("MascotActionPreview(",methods["_openGenshinRoleActions"])
        self.assertIn("viewer.exec()",methods["_openGenshinRoleActions"])
        self.assertIn("self.__onLaunchClicked(name)",methods["_openGenshinRoleActions"])
        self.assertIn("_openGenshinRoleActions(role)",
                      methods["_showGenshinLibrary"])
        # A recent role-library scan must be forwarded to the progress viewer:
        # the argument intentionally prevents a costly duplicate full scan.
        ui_method=next(node for node in ast.walk(tree)
                       if isinstance(node,ast.FunctionDef)
                       and node.name=="_showGenshinLibrary")
        progress_calls=[
            node for node in ast.walk(ui_method)
            if isinstance(node,ast.Call)
            and isinstance(node.func,ast.Attribute)
            and node.func.attr=="_showCharacterProgress"
        ]
        self.assertEqual(len(progress_calls),1)
        self.assertTrue(any(key.arg=="genshin_snapshot"
                            and isinstance(key.value,ast.Name)
                            and key.value.id=="report"
                            for key in progress_calls[0].keywords))
        self.assertIn("character_progress(",methods["_showCharacterProgress"])
        # Viewing coverage or preview must never install/download third-party assets.
        for name in ("_showCharacterProgress","_openGenshinRoleActions"):
            for term in ("install_creator_mascot(", "urlopen(", "generate_demo_roles("):
                self.assertNotIn(term,methods[name])


if __name__=="__main__":
    unittest.main()

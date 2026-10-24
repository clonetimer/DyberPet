"""Search across all 125 characters, using genuine local coverage evidence."""
from __future__ import annotations

import ast
import json
import tempfile
import unittest
from pathlib import Path

from tools.character_catalog_search import (
    describe_character_status, query_character_catalog)
from tools.character_progress import character_progress
from tools.generate_builtin_chibi_demos import generate_demo_roles
from tools.generate_mascot_demos import generate_mascot_demos


class CharacterCatalogSearchTests(unittest.TestCase):
    def setUp(self):
        td=tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.root=Path(td.name)/"res"/"role"

    def test_all_125_searchable_without_creating_assets(self):
        summary=character_progress(self.root)
        entries=summary["characters"]
        self.assertEqual(len(query_character_catalog(entries)),125)
        self.assertEqual(len(query_character_catalog(entries,family="genshin")),123)
        self.assertEqual(len(query_character_catalog(entries,family="mascot")),2)
        self.assertEqual(len(query_character_catalog(entries,status="missing")),125)
        self.assertEqual(query_character_catalog(entries,status="personal"),[])
        self.assertEqual(query_character_catalog(entries,status="demo"),[])
        self.assertFalse(self.root.exists())
        cases={"丽莎":"genshin_lisa","Lisa":"genshin_lisa",
               "GENSHIN_LISA":"genshin_lisa",
               "Doro":"mascot_doro","Dororong":"mascot_doro",
               "咕嘎":"mascot_guga","Guga":"mascot_guga"}
        for term,target in cases.items():
            with self.subTest(term=term):
                got=query_character_catalog(entries,term)
                self.assertTrue(any(v["id"]==target for v in got))
        self.assertEqual(query_character_catalog(entries,"not a known pet"),[])

    def test_filters_do_not_mislabel_original_art(self):
        generate_demo_roles(self.root,["genshin_lisa"])
        generate_mascot_demos(self.root,["doro"])
        result=character_progress(self.root)
        entries=result["characters"]
        demo=query_character_catalog(entries,status="demo")
        self.assertEqual({x["id"] for x in demo},
                         {"genshin_lisa","mascot_doro"})
        self.assertEqual(len(query_character_catalog(entries,status="missing")),123)
        self.assertEqual(query_character_catalog(entries,status="personal"),[])
        self.assertEqual(query_character_catalog(entries,"Lisa",status="demo")[0]["id"],
                         "genshin_lisa")
        self.assertIn("程序原创",describe_character_status(demo[0]))
        self.assertFalse(any(e["creator_art_and_likeness_verified"] for e in entries))
        self.assertNotIn(str(self.root),json.dumps(result,ensure_ascii=False))

    def test_invalid_filters_fail_explicitly(self):
        rows=character_progress(self.root)["characters"]
        for kind in ("garbage","GENSHIN","personal-only"):
            with self.assertRaises(ValueError):
                query_character_catalog(rows,family=kind)
            with self.assertRaises(ValueError):
                query_character_catalog(rows,status=kind)

    def test_ui_routes_to_existing_preview_and_link_management(self):
        root=Path(__file__).resolve().parents[1]
        path=root/"DyberPet"/"DyberSettings"/"CharCardUI.py"
        gui=root/"DyberPet"/"DyberSettings"/"character_catalog_dialog.py"
        source=ast.unparse(ast.parse(path.read_text("utf-8")))
        dialog=ast.unparse(ast.parse(gui.read_text("utf-8")))
        self.assertIn("self.catalogButton.clicked.connect(self._showAllCharacterCatalog)",
                      source)
        self.assertIn("CharacterCatalogDialog(",source)
        self.assertIn("self._openGenshinRoleActions(role)",source)
        self.assertIn("self._showMascotLibrary(selected.split('_', 1)[1])",source)
        self.assertIn("self._showGenshinLibrary()",source)
        self.assertIn("query_character_catalog(",dialog)
        self.assertIn("self.searchBox.textChanged.connect(self._refresh)",dialog)
        self.assertNotIn("install_creator_mascot(",dialog)
        self.assertNotIn("urlopen(",dialog)


if __name__=="__main__":
    unittest.main()

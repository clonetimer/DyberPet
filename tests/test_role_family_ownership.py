"""Prevent accidental reassignment of creator mascots as Genshin characters.

Local identity is explicitly declared by original installation receipts, never
guessed from filename, color, pose, or superficial resemblance.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.generate_mascot_demos import generate_mascot_demos
from tools.generate_builtin_chibi_demos import generate_demo_roles
from tools.genshin_library import scan_genshin_library
from tools.genshin_role_bindings import associate_existing_role, default_mapping_path
from tools.mascot_library import scan_mascot_library
from tools.role_family import known_mascot_family


class CrossFamilyOwnershipTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)/"res"/"role"

    def test_guga_and_doro_are_not_offered_as_unmapped_genshin_roles(self):
        generate_mascot_demos(self.root)
        generate_demo_roles(self.root,["genshin_lisa"])
        before={p.relative_to(self.root):p.read_bytes()
                for p in self.root.rglob("*") if p.is_file()}
        genshin=scan_genshin_library(self.root)
        mascot=scan_mascot_library(self.root)
        self.assertEqual(genshin["summary"]["other_family_folder_count"],2)
        self.assertEqual(genshin["summary"]["unmapped_folder_count"],0)
        self.assertEqual(genshin["summary"]["installed_profile_count"],1)
        self.assertEqual(mascot["summary"]["original_demo_count"],2)
        self.assertEqual(mascot["summary"]["invalid_count"],0)
        self.assertEqual(known_mascot_family(self.root/"DemoMascotGuga"),"guga")
        self.assertEqual(known_mascot_family(self.root/"DemoMascotDoro"),"doro")
        for folder in ("DemoMascotGuga","DemoMascotDoro"):
            with self.subTest(role=folder):
                with self.assertRaisesRegex(ValueError,"Guga/Doro"):
                    associate_existing_role(self.root,folder,"genshin_lisa",
                                            confirmed=True)
        self.assertFalse(default_mapping_path(self.root).exists())
        after={p.relative_to(self.root):p.read_bytes()
               for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(before,after)

    def test_source_import_cannot_be_reassigned_without_real_genshin_receipt(self):
        generate_mascot_demos(self.root,["guga"])
        folder=self.root/"DemoMascotGuga"
        (folder/"BUILTIN_MASCOT_DEMO.json").unlink()
        (folder/"IMPORT_REPORT.json").write_text(json.dumps({
            "mascot_preset":"guga","source_manifest_id":"guga--circus",
            "official_character_art_verified":False}),encoding="utf-8")
        genshin=scan_genshin_library(self.root)
        mascot=scan_mascot_library(self.root)
        self.assertEqual(genshin["summary"]["other_family_folder_count"],1)
        self.assertEqual(genshin["summary"]["unmapped_folder_count"],0)
        self.assertEqual(mascot["summary"]["imported_creator_art_count"],1)
        with self.assertRaisesRegex(ValueError,"Guga/Doro"):
            associate_existing_role(self.root,"DemoMascotGuga","genshin_amber",
                                    confirmed=True)

    def test_conflicting_receipts_are_invalid_in_both_libraries(self):
        generate_mascot_demos(self.root,["doro"])
        folder=self.root/"DemoMascotDoro"
        (folder/"PERSONAL_IMPORT.json").write_text(
            json.dumps({"selected_profile":"genshin_lisa"}),encoding="utf-8")
        gen=scan_genshin_library(self.root)
        masc=scan_mascot_library(self.root)
        self.assertEqual(gen["summary"]["installed_profile_count"],0)
        self.assertEqual(gen["summary"]["invalid_folder_count"],1)
        self.assertEqual(masc["summary"]["original_demo_count"],0)
        self.assertEqual(masc["summary"]["invalid_count"],1)
        with self.assertRaisesRegex(ValueError,"identity"):
            associate_existing_role(self.root,"DemoMascotDoro","genshin_lisa",
                                    confirmed=True)

    def test_incorrect_source_id_never_moves_to_genshin_unmapped_list(self):
        generate_mascot_demos(self.root,["guga"])
        role=self.root/"DemoMascotGuga"
        (role/"BUILTIN_MASCOT_DEMO.json").unlink()
        (role/"IMPORT_REPORT.json").write_text(json.dumps({
            "mascot_preset":"guga","source_manifest_id":"doro--lingxiaotian"
        }),encoding="utf-8")
        gen=scan_genshin_library(self.root)
        masc=scan_mascot_library(self.root)
        self.assertEqual(gen["summary"]["unmapped_folder_count"],0)
        self.assertEqual(gen["summary"]["invalid_folder_count"],1)
        self.assertEqual(masc["summary"]["invalid_count"],1)

    def test_unknown_ordinary_native_role_is_still_available_for_opt_in_mapping(self):
        generate_demo_roles(self.root,["genshin_lisa"])
        role=self.root/"DemoG_lisa"
        # Simulate a legacy import lacking family identifiers.
        (role/"BUILTIN_CHIBI_DEMO.json").unlink()
        report=scan_genshin_library(self.root)
        self.assertEqual(report["summary"]["other_family_folder_count"],0)
        self.assertEqual(report["summary"]["unmapped_folder_count"],1)
        associate_existing_role(self.root,role.name,"genshin_lisa",confirmed=True)
        updated=scan_genshin_library(self.root)
        self.assertEqual(updated["summary"]["unmapped_folder_count"],0)
        self.assertEqual(updated["summary"]["installed_profile_count"],1)


if __name__=="__main__":
    unittest.main()

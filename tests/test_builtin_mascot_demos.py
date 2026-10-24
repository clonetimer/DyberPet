"""Guga/Doro first-party demos: real moving silhouettes and no false source claims."""
from __future__ import annotations

import ast
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from tools.generate_mascot_demos import ACTIONS, MASCOTS, generate_mascot_demos
from tools.mascot_library import scan_mascot_library
from tools.install_native_role import validate_native_role


class BuiltinMascotDemosTests(unittest.TestCase):
    def setUp(self):
        td=tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.root=Path(td.name)/"res"/"role"

    def test_both_mascots_are_native_and_have_distinct_animating_silhouettes(self):
        report=generate_mascot_demos(self.root)
        self.assertEqual(set(report["mascots"]),{"guga","doro"})
        self.assertEqual(report["created"],2)
        self.assertEqual(report["frames_per_mascot"],66)
        self.assertFalse(report["actual_character_likeness_verified"])
        animations={}
        for kind,role_meta in MASCOTS.items():
            folder=self.root/role_meta["folder"]
            self.assertEqual(validate_native_role(folder),
                             {"actions":10,"images":66})
            receipt=json.loads((folder/"BUILTIN_MASCOT_DEMO.json").read_text("utf-8"))
            self.assertEqual(receipt["mascot"],kind)
            self.assertTrue(receipt["original_geometry"])
            self.assertFalse(receipt["external_artist_sprite_included"])
            self.assertFalse(receipt["game_voice_included"])
            self.assertFalse(receipt["faithful_original_art_verified"])
            self.assertEqual(receipt["visible_four_leg_walk"],kind=="doro")
            self.assertTrue((folder/"info"/"pfp.png").is_file())
            self.assertTrue((folder/"note"/"bubble_conf.json").is_file())
            sets={}
            for action,frames in ACTIONS.items():
                snapshots=[]
                for idx in range(frames):
                    with Image.open(folder/"action"/f"{action}_{idx}.png") as img:
                        self.assertEqual(img.size,(192,208))
                        self.assertIsNotNone(img.getchannel("A").getbbox())
                        snapshots.append(hashlib.sha256(img.tobytes()).hexdigest())
                sets[action]=snapshots
            self.assertGreaterEqual(len(set(sets["left_walk"])),4)
            self.assertGreaterEqual(len(set(sets["right_walk"])),4)
            self.assertGreaterEqual(len(set(sets["wave"])),3)
            self.assertGreaterEqual(len(set(sets["jump"])),3)
            self.assertGreaterEqual(len(set(sets["run"])),5)
            self.assertGreaterEqual(len(set(sets["failed"])),4)
            self.assertGreaterEqual(len(set(sets["lookaround"])),4)
            self.assertNotEqual(sets["failed"][0], sets["failed"][3])
            self.assertEqual(receipt["animation_actions"]["run"],8)
            self.assertEqual(receipt["animation_actions"]["failed"],6)
            pet=json.loads((folder/"pet_conf.json").read_text("utf-8"))
            acts=json.loads((folder/"act_conf.json").read_text("utf-8"))
            self.assertEqual(pet["fall"],"failed")
            self.assertEqual(pet["on_floor"],"jump")
            self.assertTrue(all(action in acts for action in ("run","failed","lookaround")))
            self.assertTrue(any(entry.get("act_list")==["run"] and
                                entry.get("act_prob")==0.05
                                for entry in pet["random_act"]))
            animations[kind]=sets
        self.assertNotEqual(animations["guga"]["idle"][0],
                            animations["doro"]["idle"][0])

    def test_read_only_catalog_differentiates_original_demos_and_personal_art(self):
        empty=scan_mascot_library(self.root)
        self.assertEqual(empty["summary"]["original_demo_count"],0)
        self.assertEqual(empty["summary"]["missing_demo_count"],2)
        self.assertFalse(self.root.exists())
        generate_mascot_demos(self.root)
        catalog=scan_mascot_library(self.root)
        self.assertEqual(catalog["summary"]["original_demo_count"],2)
        self.assertEqual(catalog["summary"]["imported_creator_art_count"],0)
        self.assertEqual(catalog["summary"]["missing_demo_count"],0)
        self.assertFalse(catalog["summary"]["character_likeness_verified"])
        self.assertTrue(all(not p["official_identity_verified"] and
                            not p["rights_verified"] for p in catalog["mascots"]))

    def test_no_overwrite_of_existing_user_changes(self):
        generate_mascot_demos(self.root,["doro"])
        conf=self.root/"DemoMascotDoro"/"pet_conf.json"
        conf.write_bytes(b"PREEXISTING CUSTOM DATA")
        result=generate_mascot_demos(self.root)
        self.assertEqual(result["created"],1)
        self.assertEqual(result["preserved_existing"],1)
        self.assertEqual(conf.read_bytes(),b"PREEXISTING CUSTOM DATA")

    def test_bad_claimed_creator_art_is_not_recognised(self):
        generate_mascot_demos(self.root)
        copy=self.root/"FakeDoro"
        copy.mkdir()
        (copy/"IMPORT_REPORT.json").write_text(json.dumps({
            "mascot_preset":"doro",
            "source_manifest_id":"not-author-source"
        }),encoding="utf-8")
        report=scan_mascot_library(self.root)
        self.assertEqual(report["summary"]["imported_creator_art_count"],0)
        self.assertEqual(report["summary"]["invalid_count"],1)

    def test_gui_includes_both_nonmisleading_mascot_entries(self):
        path=Path(__file__).resolve().parents[1]/"DyberPet"/"DyberSettings"/"CharCardUI.py"
        tree=ast.parse(path.read_text(encoding="utf-8"))
        funcs=[f for f in ast.walk(tree) if isinstance(f,ast.FunctionDef)
               and f.name=="_showMascotLibrary"]
        self.assertEqual(len(funcs),1)
        actual_calls=[node.func.id for node in ast.walk(funcs[0])
                      if isinstance(node,ast.Call) and isinstance(node.func,ast.Name)]
        self.assertIn("scan_mascot_library",actual_calls)
        self.assertNotIn("generate_mascot_demos",actual_calls)
        self.assertNotIn("install_native_role",actual_calls)


if __name__=="__main__":
    unittest.main()

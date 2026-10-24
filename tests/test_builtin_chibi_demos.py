"""First-party animated fallback roster: explicit demo labeling and safe install."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from tools.chibi_profiles import CHIBI_PROFILES
from tools.generate_builtin_chibi_demos import (
    ACTIONS, DEMO_ACTIONS, folder_name, generate_demo_roles)
from tools.genshin_library import scan_genshin_library
from tools.install_native_role import validate_native_role


class BuiltinChibiDemoTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name) / "res" / "role"

    def test_all_templates_have_distinct_safe_folders(self):
        keys = sorted(k for k in CHIBI_PROFILES if k.startswith("genshin_"))
        self.assertEqual(len(keys), 123)
        folders = [folder_name(k) for k in keys]
        self.assertEqual(len(set(folders)), 123)
        self.assertTrue(all(k.startswith("DemoG_") and len(k) <= 40 for k in folders))
        with self.assertRaises(ValueError):
            folder_name("../../bad")

    def test_two_distinct_real_animated_roles_never_claim_official_art(self):
        report = generate_demo_roles(self.root,
                                     ["genshin_lisa", "genshin_traveler_lumine"])
        self.assertEqual(report["created"], 2)
        self.assertEqual(report["rendered_frames_per_profile"], 66)
        self.assertFalse(report["official_game_art_included"])
        for key in ("genshin_lisa", "genshin_traveler_lumine"):
            role = self.root / folder_name(key)
            self.assertEqual(validate_native_role(role),
                             {"actions": len(DEMO_ACTIONS),
                              "images": sum(DEMO_ACTIONS.values())})
            receipt = json.loads(
                (role / "BUILTIN_CHIBI_DEMO.json").read_text("utf-8"))
            self.assertEqual(receipt["profile"], key)
            self.assertTrue(receipt["original_illustration"])
            self.assertFalse(receipt["official_character_art"])
            self.assertFalse(receipt["character_likeness_verified"])
            self.assertFalse(receipt["game_voice_included"])
            self.assertFalse((role / "PERSONAL_IMPORT.json").exists())
            pet=json.loads((role/"pet_conf.json").read_text("utf-8"))
            self.assertEqual(pet["fall"],"failed")
            self.assertEqual(pet["on_floor"],"jump")
            self.assertTrue(any(x.get("act_list")==["run"]
                                for x in pet["random_act"]))
            from hashlib import sha256
            for action,threshold in (("run",5),("failed",4),("lookaround",4)):
                digests=[
                    sha256((role/"action"/f"{action}_{i}.png").read_bytes()).hexdigest()
                    for i in range(DEMO_ACTIONS[action])
                ]
                self.assertGreaterEqual(len(set(digests)),threshold)
            with Image.open(role / "action" / "idle_0.png") as frame:
                self.assertEqual(frame.size, (192, 208))
                self.assertIsNotNone(frame.getchannel("A").getbbox())
        with Image.open(self.root / folder_name("genshin_lisa") /
                        "action" / "idle_0.png") as a, Image.open(
                            self.root / folder_name("genshin_traveler_lumine") /
                            "action" / "idle_0.png") as b:
            self.assertNotEqual(a.tobytes(), b.tobytes())
        library = scan_genshin_library(self.root)
        self.assertEqual(library["summary"]["installed_profile_count"], 2)
        self.assertEqual(library["summary"]["original_demo_profile_count"], 2)
        self.assertEqual(library["summary"]["personal_art_profile_count"], 0)
        self.assertEqual(library["summary"]["pending_template_count"], 121)
        self.assertEqual(len([x for x in library["characters"]
                              if x["status"] == "demo_installed"]), 2)
        self.assertTrue(all(not x["rights_verified"]
                            for x in library["characters"]))

    def test_rerun_preserves_modified_user_files_and_unknown_roles(self):
        key = "genshin_amber"
        generate_demo_roles(self.root, [key])
        folder = self.root / folder_name(key)
        conf = folder / "pet_conf.json"
        conf.write_text('{"my_custom_role": true}', encoding="utf-8")
        outside = self.root / "MyCharacter"
        outside.mkdir()
        (outside / "notes.txt").write_text("keep", encoding="utf-8")
        report = generate_demo_roles(self.root, [key])
        self.assertEqual(report["created"], 0)
        self.assertEqual(report["existing_preserved"], 1)
        self.assertEqual(conf.read_text("utf-8"), '{"my_custom_role": true}')
        self.assertEqual((outside / "notes.txt").read_text("utf-8"), "keep")

    def test_invalid_demo_receipt_is_not_reported_as_installed(self):
        key="genshin_lisa"
        generate_demo_roles(self.root, [key])
        file = self.root / folder_name(key) / "BUILTIN_CHIBI_DEMO.json"
        obj = json.loads(file.read_text("utf-8"))
        obj["official_character_art"] = True
        file.write_text(json.dumps(obj), encoding="utf-8")
        inventory=scan_genshin_library(self.root)
        self.assertEqual(inventory["summary"]["original_demo_profile_count"],0)
        self.assertEqual(inventory["summary"]["installed_profile_count"],0)
        self.assertEqual(inventory["summary"]["invalid_folder_count"],1)


if __name__ == "__main__":
    unittest.main()

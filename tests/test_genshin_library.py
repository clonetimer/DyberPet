"""No false 'playable' claims; read-only inventory after local Genshin imports."""
from __future__ import annotations

import ast
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from tools.genshin_library import scan_genshin_library
from tools.personal_role_import import personal_install
from tools.create_original_mascot import create_original_mascot


class LocalGenshinLibraryTests(unittest.TestCase):
    def setUp(self):
        obj = tempfile.TemporaryDirectory()
        self.addCleanup(obj.cleanup)
        self.root = Path(obj.name)
        self.roles = self.root / "res" / "role"

    def _sprite(self, path):
        path.mkdir()
        for idx in (0, 1):
            img = Image.new("RGBA", (96, 112), (0, 0, 0, 0))
            ImageDraw.Draw(img).ellipse((21 + idx * 2, 12, 68, 82),
                                        fill=(80, 177, 210, 255))
            img.save(path / f"idle_{idx}.png")

    def test_empty_catalog_is_non_creating_and_includes_lisa(self):
        out = scan_genshin_library(self.roles)
        s = out["summary"]
        self.assertEqual(s["template_count"], 123)
        self.assertEqual(s["installed_profile_count"], 0)
        self.assertEqual(s["pending_template_count"], 123)
        self.assertFalse(self.roles.exists())
        self.assertFalse(any(row["desktop_qa_verified"] or row["rights_verified"]
                             for row in out["characters"]))
        self.assertTrue(any(row["profile"] == "genshin_lisa"
                            for row in out["characters"]))

    def test_installed_profile_not_mistaken_for_real_windows_qa(self):
        source = self.root / "own-images"
        self._sprite(source)
        installed = personal_install(source, self.roles, profile="genshin_lisa",
                                     confirm_local_only=True)
        before = (installed / "PERSONAL_IMPORT.json").read_bytes()
        data = scan_genshin_library(self.roles)
        entries = {row["profile"]: row for row in data["characters"]}
        self.assertEqual(data["summary"]["installed_profile_count"], 1)
        self.assertEqual(data["summary"]["pending_template_count"], 122)
        self.assertEqual(entries["genshin_lisa"]["status"], "structurally_installed")
        self.assertEqual(len(entries["genshin_lisa"]["installed_folders"]), 1)
        self.assertFalse(entries["genshin_lisa"]["desktop_qa_verified"])
        self.assertFalse(entries["genshin_lisa"]["rights_verified"])
        self.assertEqual(entries["genshin_xiao"]["status"], "template_only")
        self.assertEqual((installed / "PERSONAL_IMPORT.json").read_bytes(), before)
        self.assertNotIn(str(self.root), json.dumps(data, ensure_ascii=False))

    def test_original_character_is_unmapped_not_a_genshin_character(self):
        create_original_mascot(self.roles)
        data = scan_genshin_library(self.roles)
        self.assertEqual(data["summary"]["installed_profile_count"], 0)
        self.assertEqual(data["summary"]["unmapped_folder_count"], 1)
        self.assertEqual(data["unmapped_local"][0]["folder"], "StarSprout")

    def test_broken_json_cannot_fake_installed_character(self):
        source = self.root / "my-art"
        self._sprite(source)
        role = personal_install(source, self.roles, profile="genshin_lisa",
                                confirm_local_only=True)
        (role / "PERSONAL_IMPORT.json").write_text(
            '{"selected_profile":', encoding="utf-8")
        data = scan_genshin_library(self.roles)
        self.assertEqual(data["summary"]["installed_profile_count"], 0)
        self.assertEqual(data["summary"]["invalid_folder_count"], 1)

    def test_conflicting_receipts_and_symlink_paths_are_rejected(self):
        source = self.root / "my-art"
        self._sprite(source)
        role = personal_install(source, self.roles, profile="genshin_lisa",
                                confirm_local_only=True)
        (role / "IMPORT_REPORT.json").write_text(
            '{"profile":"genshin_xiao"}', encoding="utf-8")
        report = scan_genshin_library(self.roles)
        self.assertEqual(report["summary"]["installed_profile_count"], 0)
        self.assertEqual(report["summary"]["invalid_folder_count"], 1)
        target = self.root / "outside"
        target.mkdir()
        link = self.roles / "BadLink"
        try:
            link.symlink_to(target, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("Symlinks require privilege on this platform")
        result = scan_genshin_library(self.roles)
        self.assertEqual(result["summary"]["invalid_folder_count"], 2)
        self.assertTrue(target.exists())

    def test_genshin_catalog_button_is_read_only(self):
        file = Path(__file__).resolve().parents[1] / "DyberPet" / "DyberSettings" / "CharCardUI.py"
        tree = ast.parse(file.read_text(encoding="utf-8"))
        methods = [n for n in ast.walk(tree)
                   if isinstance(n, ast.FunctionDef) and n.name == "_showGenshinLibrary"]
        self.assertEqual(len(methods), 1)
        call_names = []
        for node in ast.walk(methods[0]):
            if isinstance(node, ast.Call):
                target = node.func
                if isinstance(target, ast.Name):
                    call_names.append(target.id)
                elif isinstance(target, ast.Attribute):
                    call_names.append(target.attr)
        self.assertIn("scan_genshin_library", call_names)
        self.assertTrue({"personal_install", "seed", "seed_missing",
                         "install_native_role", "convert_animation_folder",
                         "requests", "urlopen"}.isdisjoint(call_names))


if __name__ == "__main__":
    unittest.main()

"""End-to-end standard Shimeji ZIP personal import without executing vendor code."""
from __future__ import annotations

import ast
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from PIL import Image

from tools.install_personal_shimeji_zip import (
    inspect_shimeji_zip, install_personal_shimeji_zip)
from tools.install_native_role import validate_native_role


class PersonalShimejiZipTests(unittest.TestCase):
    @staticmethod
    def png(color):
        out = io.BytesIO()
        Image.new("RGBA", (40, 55), color).save(out, format="PNG")
        return out.getvalue()

    def make_zip(self, directory, *, sparse=False, duplicate=False, without_clone=False):
        archive = Path(directory) / "kaveh-untrusted.zip"
        ids = (38, 1, 2, 3, 5, 6, 7, 4, 18, 19, 20, 21,
               12, 13, 14, 31, 32, 33)
        if sparse:
            ids = (38,)
        if without_clone:
            ids = tuple(n for n in ids if n != 38)
        with zipfile.ZipFile(archive, "w") as z:
            z.writestr("Shimeji.exe", b"never execute this")
            z.writestr("libs/SomeRuntime.jar", b"do not extract this")
            z.writestr("../path-traversal.txt", b"not extracted")
            for idx in ids:
                z.writestr(f"Pet/img/shime{idx}.png",
                           self.png((idx * 5 % 255, idx * 11 % 255, 50, 230)))
            if duplicate:
                z.writestr("Other/img/shime38.png", self.png((2, 3, 4, 255)))
        return archive

    def test_import_real_pngs_preserves_original_bytes_and_skips_executables(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = self.make_zip(tmp)
            origin = inspect_shimeji_zip(archive)
            root = Path(tmp) / "roles"
            with self.assertRaises(ValueError):
                install_personal_shimeji_zip(archive, root,
                    profile="genshin_kaveh")
            self.assertFalse(root.exists())
            dest = install_personal_shimeji_zip(
                archive, root, profile="genshin_kaveh", confirmed=True)
            self.assertEqual((dest/"source_frames"/"shime38.png").read_bytes(),
                             origin[38])
            self.assertEqual((dest/"action"/"stand_0.png").read_bytes(), origin[1])
            self.assertFalse((dest/"Shimeji.exe").exists())
            self.assertFalse((dest/"libs").exists())
            self.assertFalse((Path(tmp)/"path-traversal.txt").exists())
            validation = validate_native_role(dest)
            self.assertGreaterEqual(validation["actions"], 5)\n            act_conf = json.loads((dest/"act_conf.json").read_text("utf-8"))\n            self.assertNotIn("patpat", act_conf)\n            self.assertIn("rest", act_conf)
            self.assertTrue((dest/"ANIMATION_PREVIEW.png").is_file())
            receipt = json.loads((dest/"PERSONAL_IMPORT.json").read_text("utf-8"))
            self.assertEqual(receipt["selected_profile"], "genshin_kaveh")
            self.assertFalse(receipt["source_upstream_identity_verified"])
            self.assertFalse(receipt["likeness_manually_reviewed"])
            self.assertFalse(receipt["redistribution_allowed_by_tool"])
            self.assertEqual(receipt["all_original_frames_preserved"], len(origin))
            second = install_personal_shimeji_zip(
                archive, root, profile="genshin_kaveh", confirmed=True)
            self.assertNotEqual(second, dest)
            self.assertTrue(dest.exists())

    def test_actual_gui_has_explicit_png_only_zip_route(self):
        gui_path = Path(__file__).resolve().parents[1] / "DyberPet" / "DyberSettings" / "CharCardUI.py"
        source = gui_path.read_text("utf-8")
        ast.parse(source)
        self.assertIn("个人本地导入：Shimeji 原画 ZIP（仅提取图片）", source)
        self.assertIn("mode=\"shimeji_zip\"", source)
        self.assertIn('elif self.mode == "shimeji_zip":', source)
        self.assertIn("install_personal_shimeji_zip(", source)

    def test_missing_required_frames_and_duplicate_names_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = self.make_zip(tmp, sparse=True)
            with self.assertRaisesRegex(ValueError, "requires stand 1"):
                inspect_shimeji_zip(source)
        with tempfile.TemporaryDirectory() as tmp:
            source = self.make_zip(tmp, duplicate=True)
            with self.assertRaisesRegex(ValueError, "Duplicate"):
                inspect_shimeji_zip(source)

    def test_standard_idle_and_walk_work_even_without_clone_frame38(self):
        with tempfile.TemporaryDirectory() as td:
            archive = self.make_zip(td, without_clone=True)
            frames = inspect_shimeji_zip(archive)
            self.assertIn(1, frames)
            self.assertNotIn(38, frames)
            role = install_personal_shimeji_zip(
                archive, Path(td) / "roles", profile="genshin_kaveh",
                confirmed=True)
            self.assertEqual((role / "action" / "stand_0.png").read_bytes(), frames[1])
            act = json.loads((role / "act_conf.json").read_text("utf-8"))
            self.assertNotIn("patpat", act)
            self.assertIn("rest", act)

    def test_wrong_profile_and_nonzip_are_not_silently_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = self.make_zip(tmp)
            with self.assertRaisesRegex(ValueError, "exact Genshin identity"):
                install_personal_shimeji_zip(
                    source, Path(tmp)/"roles", profile="unknown", confirmed=True)
            with self.assertRaises(ValueError):
                inspect_shimeji_zip(Path(tmp)/"missing.zip")


if __name__ == "__main__":
    unittest.main()

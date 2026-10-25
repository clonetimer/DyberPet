"""Personal Codex ZIP import: pixel preservation and executable isolation."""
from __future__ import annotations

import ast
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from PIL import Image, ImageDraw

from tools.install_personal_codex_zip import inspect_codex_zip, install_personal_codex_zip
from tools.install_native_role import validate_native_role


class CodexZipTests(unittest.TestCase):
    def make_archive(self, root, *, duplicate=False, traversal=False, wrong_manifest=False):
        image = Image.new("RGBA", (1536, 1872), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        for row in range(9):
            for col in range(6 if row == 0 else 4):
                x, y = col * 192, row * 208
                draw.rectangle((x + 54, y + 14, x + 132, y + 193),
                               fill=((40 + col * 27) % 255, (80 + row * 17) % 255, 120, 255))
        stream = BytesIO()
        image.save(stream, format="WEBP", lossless=True)
        sheet = stream.getvalue()
        source = Path(root) / "pet.zip"
        manifest = {
            "id": "community-kaveh",
            "displayName": "Kaveh example",
            "spriteVersionNumber": 1,
            "spritesheetPath": "../unsafe.webp" if wrong_manifest else "spritesheet.webp",
        }
        with zipfile.ZipFile(source, "w", compression=zipfile.ZIP_STORED) as z:
            z.writestr("kaveh/pet.json", json.dumps(manifest))
            z.writestr("kaveh/spritesheet.webp", sheet)
            z.writestr("kaveh/run.exe", b"never copied or executed")
            z.writestr("kaveh/libs/extension.jar", b"not a dependency")
            if duplicate:
                z.writestr("other/pet.json", json.dumps(manifest))
            if traversal:
                z.writestr("../attacker.txt", b"not allowed")
        return source, sheet

    def test_actual_atlas_pixels_and_receipt_are_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, sheet = self.make_archive(tmp)
            data = inspect_codex_zip(source)
            self.assertEqual(data["version"], 1)
            self.assertEqual(data["sheet"], sheet)
            roles = Path(tmp) / "roles"
            with self.assertRaisesRegex(ValueError, "Explicit confirmation"):
                install_personal_codex_zip(source, roles, profile="genshin_kaveh")
            self.assertFalse(roles.exists())
            new = install_personal_codex_zip(
                source, roles, profile="genshin_kaveh", confirmed=True)
            self.assertTrue(new.is_dir())
            self.assertFalse((new / "run.exe").exists())
            self.assertFalse((new / "libs").exists())
            check = validate_native_role(new)
            self.assertGreaterEqual(check["actions"], 5)
            self.assertGreaterEqual(check["images"], 15)
            receipt = json.loads((new / "PERSONAL_IMPORT.json").read_text("utf-8"))
            self.assertEqual(receipt["selected_profile"], "genshin_kaveh")
            self.assertTrue(receipt["source_original_frames_preserved"])
            self.assertFalse(receipt["likeness_manually_reviewed"])
            self.assertFalse(receipt["source_creator_identity_verified"])
            self.assertFalse(receipt["redistribution_allowed_by_tool"])
            another = install_personal_codex_zip(
                source, roles, profile="genshin_kaveh", confirmed=True)
            self.assertNotEqual(new, another)
            self.assertTrue(new.is_dir())

    def test_traversal_duplicated_and_wrong_path_refused(self):
        for mode, phrase in (("traversal", "Unsafe ZIP"),
                             ("duplicate", "Ambiguous duplicate"),
                             ("wrong_manifest", "Unsafe or unsupported")):
            with tempfile.TemporaryDirectory() as tmp:
                kw = {mode: True}
                source, _ = self.make_archive(tmp, **kw)
                with self.assertRaisesRegex(ValueError, phrase):
                    inspect_codex_zip(source)

    def test_exact_profile_required_and_gui_path_is_wired(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, _ = self.make_archive(tmp)
            with self.assertRaisesRegex(ValueError, "exact Genshin character"):
                install_personal_codex_zip(
                    source, Path(tmp)/"roles", profile="unknown", confirmed=True)
        gui = (Path(__file__).resolve().parents[1] /
               "DyberPet" / "DyberSettings" / "CharCardUI.py").read_text("utf-8")
        ast.parse(gui)
        self.assertIn("个人本地导入：Codex 动画 ZIP（仅提取图集）", gui)
        self.assertIn('elif self.mode == "codex_zip":', gui)
        self.assertIn("install_personal_codex_zip(", gui)


if __name__ == "__main__":
    unittest.main()

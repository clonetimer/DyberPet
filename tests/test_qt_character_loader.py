"""Real PySide6 loader smoke test for generated Q-style character role data.

Run on a Windows GitHub runner with PySide6 and Pillow installed, using
headless Qt. This calls the *actual* DyberPet.conf.PetConfig.init_config,
rather than testing only JSON compatibility.
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image, ImageDraw
from tools.import_chibi_animations import convert_animation_folder


class QtCharacterLoaderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from PySide6.QtWidgets import QApplication
        except ImportError as exc:
            raise unittest.SkipTest("PySide6 is only installed in the GUI loader smoke job") from exc
        cls.app = QApplication.instance() or QApplication([])

    def test_role_conversion_and_actual_qt_animation_loader(self):
        from PySide6.QtGui import QPixmap
        from DyberPet.conf import PetConfig, CheckCharFiles

        role_root = Path(__file__).resolve().parents[1] / "res" / "role"
        role_name = "SyntheticChibiQtSmoke"
        role_dir = role_root / role_name
        self.assertFalse(role_dir.exists(), "Test role already exists")
        try:
            with tempfile.TemporaryDirectory() as temp:
                source = Path(temp) / "Source"
                source.mkdir()
                for act in ("idle", "wave", "right_walk", "left_walk", "jump"):
                    for frame_number in range(2):
                        img = Image.new("RGBA", (192, 208), (0, 0, 0, 0))
                        ImageDraw.Draw(img).ellipse(
                            (50 + frame_number, 30, 140 + frame_number, 175),
                            fill=(115, 165, 219, 255)
                        )
                        img.save(source / f"{act}_{frame_number}.png")
                converted = convert_animation_folder(
                    source, role_root, folder=role_name, profile="genshin_nahida")
                self.assertEqual(converted, role_dir)
                self.assertEqual(CheckCharFiles(str(role_dir))[0], 0)
                frames = {}
                for path in (role_dir / "action").glob("*.png"):
                    bitmap = QPixmap(str(path))
                    self.assertFalse(bitmap.isNull(), str(path))
                    frames[path.stem] = bitmap
                pet = PetConfig.init_config(role_name, frames)
                self.assertGreater(pet.width, 0)
                self.assertEqual(pet.petname, role_name)
                self.assertEqual(len(pet.default.images), 2)
                self.assertGreater(len(pet.patpat[0].images), 0)
                self.assertIn("idle", pet.act_dict)
                self.assertIn("wave", pet.act_dict)
                self.assertGreater(sum(pet.act_prob), 0.99)
                self.assertLess(sum(pet.act_prob), 1.01)
        finally:
            if role_dir.exists():
                shutil.rmtree(role_dir)


    def test_native_zip_install_and_actual_qt_loader(self):
        import json
        import zipfile
        from PySide6.QtGui import QPixmap
        from DyberPet.conf import PetConfig, CheckCharFiles
        from tools.install_native_role import install_native_role

        role_root = Path(__file__).resolve().parents[1] / "res" / "role"
        name = "SyntheticNativeZipQtSmoke"
        target = role_root / name
        self.assertFalse(target.exists())
        try:
            with tempfile.TemporaryDirectory() as tmp:
                source = Path(tmp) / "Native"
                (source / "action").mkdir(parents=True)
                Image.new("RGBA", (192, 208), (90, 120, 180, 220)).save(
                    source / "action" / "idle_0.png")
                (source / "pet_conf.json").write_text(json.dumps({
                    "default": "idle", "drag": "idle", "fall": "idle",
                    "focus": "idle", "patpat": "idle",
                    "random_act": [{"name": "站立", "act_list": ["idle"]}]
                }), encoding="utf-8")
                (source / "act_conf.json").write_text(json.dumps({
                    "idle": {"images": "idle", "frame_refresh": 0.18}
                }), encoding="utf-8")
                archive = Path(tmp) / "native.zip"
                with zipfile.ZipFile(archive, "w") as writer:
                    for file in source.rglob("*"):
                        if file.is_file():
                            writer.write(file, "Role/" + file.relative_to(source).as_posix())
                installed = install_native_role(archive, role_root, role_folder=name)
                self.assertEqual(installed, target)
                self.assertEqual(CheckCharFiles(str(target))[0], 0)
                pics = {"idle_0": QPixmap(str(target / "action" / "idle_0.png"))}
                self.assertFalse(pics["idle_0"].isNull())
                pet = PetConfig.init_config(name, pics)
                self.assertEqual(len(pet.act_dict["idle"].images), 1)
                self.assertIsNotNone(pet.focus)
        finally:
            if target.exists():
                shutil.rmtree(target)


if __name__ == "__main__":
    unittest.main()

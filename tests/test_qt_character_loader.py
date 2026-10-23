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


if __name__ == "__main__":
    unittest.main()

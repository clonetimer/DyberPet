"""Real Blender smoke: synthetic original mascot -> RGBA PNG -> DyberPet role.

Requires Blender installed and BLENDER_BIN environment variable or blender on PATH.
This is a separate CI job to avoid installing a large 3D dependency for every
2D character importer unit test.
"""
from __future__ import annotations
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from tools.render_chibi_blender import render_blender
from tools.import_chibi_animations import convert_animation_folder
from tools.install_native_role import validate_native_role


class RealBlenderDemoTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (os.environ.get("BLENDER_BIN") or shutil.which("blender")):
            raise unittest.SkipTest("Real Blender smoke runs only when Blender is installed")

    def test_synthetic_blender_to_dyberpet_role(self):
        blender = os.environ.get("BLENDER_BIN", "blender")
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            rendered = render_blender(
                blender, base / "frames", demo=True,
                frames=2, actions=("idle", "left_walk", "wave"),
                timeout=600
            )
            report = json.loads(
                (rendered / "BLENDER_RENDER_REPORT.json").read_text("utf-8"))
            self.assertTrue(report["demo"])
            self.assertEqual(report["renderer"], "Blender")
            self.assertEqual(report["frame_qa"]["idle"]["frames"], 2)
            role = convert_animation_folder(
                rendered, base / "roles", folder="SyntheticOriginalChibi",
                profile="chibi", author="DyberPet CI synthetic original geometry"
            )
            preflight = validate_native_role(role)
            self.assertGreaterEqual(preflight["actions"], 3)
            self.assertTrue((role / "ANIMATION_PREVIEW.png").is_file())
            self.assertTrue((role / "info" / "pfp.png").is_file())


if __name__ == "__main__":
    unittest.main()

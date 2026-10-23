"""Real Blender smoke: synthetic original mascot -> RGBA PNG -> DyberPet role.

Requires Blender installed and BLENDER_BIN environment variable or blender on PATH.
This is a separate CI job to avoid installing a large 3D dependency for every
2D character importer unit test.
"""
from __future__ import annotations
import json
import os
import shutil
import subprocess
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
            artifacts = os.environ.get("BLENDER_CI_ARTIFACT_DIR")
            if artifacts:
                directory = Path(artifacts)
                directory.mkdir(parents=True, exist_ok=True)
                for name in ("ANIMATION_PREVIEW.png", "IMPORT_REPORT.json"):
                    shutil.copy2(role / name, directory / name)
                for name in ("idle_0.png", "wave_0.png"):
                    shutil.copy2(rendered / name, directory / name)
                shutil.copy2(rendered / "BLENDER_RENDER_REPORT.json",
                             directory / "BLENDER_RENDER_REPORT.json")


    def test_exported_original_glb_import_pipeline(self):
        blender = os.environ.get("BLENDER_BIN", "blender")
        scene_script = (Path(__file__).resolve().parents[1] /
                        "tools" / "blender_demo_export.py")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            model = root / "OriginalSyntheticChibi.glb"
            run = subprocess.run(
                [blender, "--background", "--factory-startup", "--disable-autoexec",
                 "--python-exit-code", "23", "--python", str(scene_script),
                 "--", str(model)],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, timeout=180, check=False
            )
            self.assertEqual(run.returncode, 0, run.stdout[-2500:])
            self.assertTrue(model.exists())
            frames = render_blender(
                blender, root / "imported_frames", source=model,
                frames=2, actions=("idle", "wave"), timeout=600
            )
            report = json.loads(
                (frames / "BLENDER_RENDER_REPORT.json").read_text("utf-8"))
            self.assertFalse(report["demo"])
            self.assertIn("root-motion-only", report["animation_quality"])
            role = convert_animation_folder(
                frames, root / "roles", folder="ImportedOriginalGLB",
                profile="chibi", author="DyberPet original synthetic geometry"
            )
            self.assertGreater(validate_native_role(role)["images"], 1)


if __name__ == "__main__":
    unittest.main()

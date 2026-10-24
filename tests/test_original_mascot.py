"""Real playable role generated from original drawing code: no external assets."""
import ast
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from tools.create_original_mascot import ACTIONS, CELL, create_original_mascot
from tools.install_native_role import validate_native_role


class OriginalMascotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_real_role_frames_actions_preview_and_no_copyrighted_assets(self):
        role = create_original_mascot(self.root / "out")
        self.assertEqual(role.name, "StarSprout")
        self.assertTrue((role / "ANIMATION_PREVIEW.png").is_file())
        self.assertTrue((role / "info" / "cover.png").is_file())
        self.assertTrue((role / "info" / "pfp.png").is_file())
        pet = json.loads((role / "pet_conf.json").read_text("utf-8"))
        self.assertEqual(pet["default"], "idle")
        self.assertIn(pet["left"], ACTIONS)
        self.assertIn(pet["right"], ACTIONS)
        result = validate_native_role(role)
        self.assertEqual(result["images"], sum(ACTIONS.values()))
        self.assertEqual(result["actions"], len(ACTIONS))
        for action, count in ACTIONS.items():
            with self.subTest(action=action):
                frames = sorted((role / "action").glob(action + "_*.png"))
                self.assertEqual(len(frames), count)
                unique = set()
                for frame in frames:
                    with Image.open(frame) as img:
                        self.assertEqual(img.size, CELL)
                        self.assertIsNotNone(img.getchannel("A").getbbox())
                        unique.add(hashlib.sha256(img.convert("RGBA").tobytes()).digest())
                self.assertGreater(len(unique), 1,
                                   "Action must have real changing frames: " + action)
        metadata = json.loads((role / "ORIGINAL_GENERATION.json").read_text("utf-8"))
        self.assertFalse(metadata["third_party_art"])
        self.assertFalse(metadata["third_party_voice"])
        self.assertTrue(metadata["manual_windows_qa_required"])
        self.assertFalse(metadata["automated_runtime_qa"])

    def test_no_overwrite_and_new_role_name_is_allocated(self):
        one = create_original_mascot(self.root)
        protected = (one / "pet_conf.json").read_bytes()
        two = create_original_mascot(self.root)
        self.assertNotEqual(one, two)
        self.assertEqual(two.name, "StarSprout_2")
        self.assertEqual((one / "pet_conf.json").read_bytes(), protected)
        with self.assertRaises(FileExistsError):
            create_original_mascot(self.root, folder="StarSprout")
        self.assertEqual((one / "pet_conf.json").read_bytes(), protected)

    def test_unsafe_explicit_names_do_not_create_any_directory(self):
        root = self.root / "outputs"
        for bad in ("../escape", "foo/bar", ".", "", "1bad", "bad\\name"):
            with self.subTest(name=bad):
                with self.assertRaises(ValueError):
                    create_original_mascot(root, folder=bad)
        self.assertFalse(root.exists())

    def test_cli_generates_valid_role_and_json_receipt(self):
        repo = Path(__file__).resolve().parents[1]
        p = subprocess.run([
            sys.executable, str(repo / "tools" / "create_original_mascot.py"),
            "--output-root", str(self.root / "cli"),
        ], capture_output=True, text=True, encoding="utf-8", timeout=45,
           check=True)
        receipt = json.loads(p.stdout)
        self.assertTrue(receipt["generated"])
        self.assertTrue(receipt["requires_manual_qa"])
        self.assertTrue(Path(receipt["role"]).exists())

    def test_gui_add_role_entry_uses_worker_not_ui_thread(self):
        repo = Path(__file__).resolve().parents[1]
        file = repo / "DyberPet" / "DyberSettings" / "CharCardUI.py"
        tree = ast.parse(file.read_text(encoding="utf-8"))
        ui = next(v for v in ast.walk(tree) if isinstance(v, ast.FunctionDef)
                  and v.name == "_importOriginalDemo")
        worker = next(v for v in ast.walk(tree) if isinstance(v, ast.FunctionDef)
                      and v.name == "run" and "ChibiImportThread"
                      in file.read_text(encoding="utf-8"))
        self.assertIn("original_demo", ast.unparse(ui))
        self.assertIn("ChibiImportThread", ast.unparse(ui))
        self.assertIn("create_original_mascot", ast.unparse(worker))


if __name__ == "__main__":
    unittest.main()

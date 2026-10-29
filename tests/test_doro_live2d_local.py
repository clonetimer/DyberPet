"""R52: real Cubism local model inventory, without storing third-party Doro art."""
from __future__ import annotations
import json
import os
import tempfile
import unittest
from pathlib import Path

from tools.doro_live2d_local import inspect_local_live2d


class DoroLocalModelTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root = Path(t.name)
        self.folder = self.root / "Doro"
        self.folder.mkdir()
        self._make("Doro.moc3")
        self._make("texture.png")
        self._make("idle.motion3.json")
        self._make("happy.exp3.json")
        self.model = self.folder / "Doro.model3.json"
        self.data = {
            "Version": 3,
            "FileReferences": {
                "Moc": "Doro.moc3", "Textures": ["texture.png"],
                "Motions": {"Idle": [{"File": "idle.motion3.json"}]},
                "Expressions": [{"Name": "happy", "File": "happy.exp3.json"}],
            }
        }
        self._save()

    def _make(self, name):
        path = self.folder / name
        path.write_bytes(b"TEST_ONLY_NOT_A_REAL_DORO_MODEL")

    def _save(self):
        self.model.write_text(json.dumps(self.data), encoding="utf-8")

    def test_local_model_inventory_no_modifications_and_no_approval_claim(self):
        before = {x.name: x.read_bytes() for x in self.folder.iterdir()}
        result = inspect_local_live2d(self.model)
        self.assertEqual(result["resource_files_checked"], 4)
        self.assertEqual(result["motion_groups"], {"Idle": 1})
        self.assertEqual(result["expressions"], ["happy"])
        self.assertFalse(result["is_user_approved_doro_likeness"])
        self.assertFalse(result["independent_orthographic_threeview_complete"])
        self.assertFalse(result["redistribution_rights_verified"])
        self.assertEqual(before, {x.name: x.read_bytes() for x in self.folder.iterdir()})

    def test_reject_parent_directory_traversal(self):
        self.data["FileReferences"]["Moc"] = "../Doro.moc3"
        self._save()
        with self.assertRaisesRegex(ValueError, "below model directory"):
            inspect_local_live2d(self.model)

    def test_reject_remote_or_absolute_resources(self):
        for name in ("https://example.com/asset.png", "/tmp/asset.png",
                     "C:/Windows/asset.png", "\\\\server\\share\\asset.png"):
            self.data["FileReferences"]["Textures"] = [name]
            self._save()
            with self.subTest(name=name), self.assertRaises(ValueError):
                inspect_local_live2d(self.model)

    def test_missing_art_blocks_preview(self):
        (self.folder / "texture.png").unlink()
        with self.assertRaisesRegex(ValueError, "Missing"):
            inspect_local_live2d(self.model)

    def test_missing_motions_are_not_fabricated(self):
        self.data["FileReferences"]["Motions"] = {}
        self._save()
        result = inspect_local_live2d(self.model)
        self.assertEqual(result["motion_groups"], {})

    def test_duplicate_reference_refused(self):
        self.data["FileReferences"]["Textures"] = ["texture.png", "texture.png"]
        self._save()
        with self.assertRaisesRegex(ValueError, "repeated"):
            inspect_local_live2d(self.model)

    def test_symlink_to_outside_refused(self):
        link = self.folder / "foreign.png"
        try:
            link.symlink_to(self.root / "outside.png")
        except (NotImplementedError, OSError):
            self.skipTest("Symlink not permitted by runner")
        self.data["FileReferences"]["Textures"] = ["foreign.png"]
        self._save()
        with self.assertRaisesRegex(ValueError, "linked"):
            inspect_local_live2d(self.model)

    def test_qt_dialog_hook_has_real_doro_only_action(self):
        source = (Path(__file__).resolve().parents[1]
                  / "DyberPet" / "DyberSettings" / "CharCardUI.py").read_text("utf-8")
        self.assertIn("【Doro 专项】", source)
        self.assertIn("from .doro_live2d_dialog import open_doro_live2d", source)
        self.assertIn("open_doro_live2d(self)", source)

    def test_qt_preview_module_compiles_without_optional_engine_import(self):
        import ast
        file = (Path(__file__).resolve().parents[1]
                / "DyberPet" / "DyberSettings" / "doro_live2d_dialog.py")
        tree = ast.parse(file.read_text(encoding="utf-8"))
        self.assertTrue(any(isinstance(n, ast.ClassDef)
                            and n.name == "_DoroGLView" for n in tree.body))
        self.assertTrue(any(isinstance(n, ast.ClassDef)
                            and n.name == "DoroLive2DPreviewDialog"
                            for n in tree.body))


if __name__ == "__main__":
    unittest.main()

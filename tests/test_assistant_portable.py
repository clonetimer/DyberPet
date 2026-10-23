"""Portable root bootstrap: real files, no change to source interpreter cwd."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from DyberPet.assistant.portable import initialize_portable_directory, inspect_assets


class PortableStartupTests(unittest.TestCase):
    def test_unfrozen_source_keeps_working_directory(self):
        original = Path.cwd()
        with tempfile.TemporaryDirectory() as folder:
            self.assertIsNone(initialize_portable_directory(False, Path(folder) / "DyberPet.exe"))
        self.assertEqual(Path.cwd(), original)

    def test_frozen_executable_changes_to_exe_directory(self):
        original = Path.cwd()
        try:
            with tempfile.TemporaryDirectory() as folder:
                binary = Path(folder) / "DyberPet.exe"
                self.assertEqual(initialize_portable_directory(True, binary), Path(folder).resolve())
                self.assertEqual(Path.cwd(), Path(folder).resolve())
        finally:
            os.chdir(original)

    def test_explicit_missing_assets_prevent_false_smoke_pass(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertFalse(inspect_assets(folder)["ok"])
            self.assertIn("res/language/language.json", inspect_assets(folder)["missing"])

    def test_actual_source_assets_have_required_runtime_files(self):
        project = Path(__file__).resolve().parents[1]
        result = inspect_assets(project)
        self.assertTrue(result["ok"], repr(result["missing"]))


if __name__ == "__main__":
    unittest.main()

"""Cross-platform unit acceptance of Linux frozen-root handling."""
from __future__ import annotations

import ast
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from DyberPet.assistant.portable import (
    resource_root, initialize_portable_directory, inspect_assets)


class LinuxPortablePathTests(unittest.TestCase):
    def test_source_finds_repo_parent_not_cwd(self):
        source = Path(__file__).resolve().parents[1] / "DyberPet" / "settings.py"
        self.assertEqual(resource_root(source, frozen=False),
                         Path(__file__).resolve().parents[1])
        self.assertTrue(inspect_assets(resource_root(source, frozen=False))["ok"])

    def test_frozen_uses_executable_location_even_if_module_path_is_internal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            exe = root / "DyberPet"
            source = root / "_internal" / "DyberPet" / "settings.py"
            self.assertEqual(resource_root(source, frozen=True, executable=exe),
                             root.resolve())
            self.assertNotEqual(resource_root(source, frozen=False), root.resolve())

    def test_frozen_bootstrap_switches_to_executable_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            old = Path.cwd()
            try:
                with patch("os.chdir", wraps=os.chdir) as change:
                    result = initialize_portable_directory(
                        frozen=True, executable=base / "DyberPet")
                self.assertEqual(result, base.resolve())
                self.assertEqual(Path.cwd(), base.resolve())
                self.assertTrue(change.called)
            finally:
                os.chdir(old)

    def test_settings_and_conf_share_resource_root(self):
        root = Path(__file__).resolve().parents[1]
        for name in ("settings.py", "conf.py"):
            with self.subTest(file=name):
                tree = ast.parse((root / "DyberPet" / name).read_text("utf-8"))
                invokes = [n for n in ast.walk(tree)
                           if isinstance(n, ast.Call)
                           and isinstance(n.func, ast.Name)
                           and n.func.id == "resource_root"]
                self.assertTrue(invokes)
                self.assertEqual(ast.unparse(invokes[0]), "resource_root(__file__)")


if __name__ == "__main__":
    unittest.main()

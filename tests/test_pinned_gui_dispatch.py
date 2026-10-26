"""Test actual character GUI worker dispatch without requiring Qt to load.

Extract the unmodified ChibiImportThread.run AST, execute that method
with only mocked framework surface, and assert the exact archive passed to
the real installer boundary. This catches Path('kaveh') identity mistakes.
"""
from __future__ import annotations

import ast
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


class _Done:
    def __init__(self):
        self.calls = []

    def emit(self, role, error):
        self.calls.append((role, error))


class _Worker:
    def __init__(self, *, mode, source, preset, root):
        self.mode = mode
        self.source = Path(source)  # mirrors the actual QThread constructor
        self.preset = preset
        self.profile = None
        self.folder = None
        self.output_root = root
        self.done = _Done()


def _actual_worker_run():
    source = (Path(__file__).resolve().parents[1] /
              "DyberPet/DyberSettings/CharCardUI.py").read_text("utf-8")
    tree = ast.parse(source)
    cls = next(node for node in tree.body if
               isinstance(node, ast.ClassDef) and node.name == "ChibiImportThread")
    run = next(node for node in cls.body if
               isinstance(node, ast.FunctionDef) and node.name == "run")
    isolated = ast.fix_missing_locations(ast.Module(body=[run], type_ignores=[]))
    env = {
        "CheckCharFiles": lambda path: (0, ""),
        "rmtree": lambda path, ignore_errors=False: None,
    }
    exec(compile(isolated, "CharCardUI.py", "exec"), env)
    return env["run"]


class PinnedSourceGuiWorkerDispatch(unittest.TestCase):
    def test_online_mode_passes_string_identity_not_path(self):
        run = _actual_worker_run()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            output = root / "SourcePetDbKaveh"
            output.mkdir()
            caller = _Worker(mode="pinned_codexpetdb", source="kaveh",
                             preset="kaveh", root=root)
            with patch("tools.install_pinned_codexpetdb.install_pinned_codexpetdb",
                       return_value=output) as install:
                run(caller)
            self.assertEqual(caller.done.calls, [(output.name, "")])
            self.assertEqual(install.call_args.args, ("kaveh", root))
            self.assertIs(type(install.call_args.args[0]), str)
            self.assertTrue(install.call_args.kwargs["confirmed"])
            self.assertIsNone(install.call_args.kwargs["archive"])

    def test_offline_mode_preserves_selected_identity_and_local_file(self):
        run = _actual_worker_run()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / "gi-kirara.zip"
            path.write_bytes(b"test-only")
            output = root / "SourcePetDbKirara"
            output.mkdir()
            caller = _Worker(mode="pinned_codexpetdb_local", source=path,
                             preset="kirara", root=root)
            with patch("tools.install_pinned_codexpetdb.install_pinned_codexpetdb",
                       return_value=output) as install:
                run(caller)
            self.assertEqual(caller.done.calls, [(output.name, "")])
            self.assertEqual(install.call_args.args, ("kirara", root))
            self.assertEqual(install.call_args.kwargs["archive"], path)

    def test_online_and_offline_workers_do_not_claim_success_on_hash_failure(self):
        run = _actual_worker_run()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            existing = root / "OlderPet"
            existing.mkdir()
            for mode in ("pinned_codexpetdb", "pinned_codexpetdb_local"):
                caller = _Worker(mode=mode, source="gi-kaveh.zip" if
                                 mode.endswith("_local") else "kaveh",
                                 preset="kaveh", root=root)
                with patch("tools.install_pinned_codexpetdb.install_pinned_codexpetdb",
                           side_effect=ValueError("ZIP SHA-256 mismatch")):
                    run(caller)
                self.assertEqual(caller.done.calls,
                                 [("", "ZIP SHA-256 mismatch")])
                self.assertTrue(existing.exists())

    def test_catalog_ui_lists_both_paths_with_independent_opt_in(self):
        source = (Path(__file__).resolve().parents[1] /
                  "DyberPet/DyberSettings/CharCardUI.py").read_text("utf-8")
        ast.parse(source)
        self.assertIn('self._importPinnedPetDb(local_archive=True)', source)
        self.assertIn('"pinned_codexpetdb_local" if local_archive', source)
        self.assertIn('profile=None, preset=options[selected], folder=None)', source)
        self.assertIn('return petdb[key]["profile"]', source)
        self.assertIn("固定原画 ZIP（断网可用）", source)


if __name__ == "__main__":
    unittest.main()

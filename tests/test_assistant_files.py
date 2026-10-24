"""Portable tests for explicitly user-controlled file actions."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from DyberPet.assistant.files import PetWorkspace, WorkspaceError


class PetFilesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "pet"
        self.workspace = PetWorkspace(self.root)

    def test_create_delete_restore_roundtrip(self):
        path = self.workspace.create("note.txt", "测试角色内容\nhello")
        self.assertEqual(path.read_text("utf-8"), "测试角色内容\nhello")
        self.assertEqual(self.workspace.list_files(), ["note.txt"])
        key = self.workspace.soft_delete("note.txt")
        self.assertFalse(path.exists())
        self.assertEqual(self.workspace.deleted_files(), [key])
        restored = self.workspace.restore(key)
        self.assertEqual(restored, path)
        self.assertEqual(path.read_text("utf-8"), "测试角色内容\nhello")

    def test_no_overwrite_even_with_retry(self):
        self.workspace.create("a.md", "first")
        with self.assertRaisesRegex(WorkspaceError, "overwrite"):
            self.workspace.create("a.md", "second")
        self.assertEqual((self.root / "a.md").read_text("utf-8"), "first")

    def test_path_traversal_rejected(self):
        for name in ("../outside.txt", "a/b.txt", r"a\b.txt",
                     "/tmp/target.txt", "bad.exe", "CON.txt",
                     "a.txt.", ".hidden.txt", "hello.txt:stream"):
            with self.subTest(name=name), self.assertRaises(WorkspaceError):
                self.workspace.create(name, "x")
        self.assertFalse((self.root.parent / "outside.txt").exists())

    def test_large_file_rejected(self):
        with self.assertRaisesRegex(WorkspaceError, "256 KiB"):
            self.workspace.create("huge.txt", "z" * 300000)
        self.assertEqual(self.workspace.list_files(), [])

    def test_restore_conflict_never_overwrites(self):
        self.workspace.create("a.txt", "old")
        key = self.workspace.soft_delete("a.txt")
        self.workspace.create("a.txt", "new")
        with self.assertRaisesRegex(WorkspaceError, "already exists"):
            self.workspace.restore(key)
        self.assertEqual((self.root / "a.txt").read_text("utf-8"), "new")
        self.assertIn(key, self.workspace.deleted_files())

    def test_symlinks_not_mutated(self):
        original = self.root.parent / "private.txt"
        original.write_text("must remain", encoding="utf-8")
        try:
            (self.root / "linked.txt").symlink_to(original)
        except (OSError, NotImplementedError):
            self.skipTest("OS blocks symlinks")
        with self.assertRaisesRegex(WorkspaceError, "Symbolic links"):
            self.workspace.soft_delete("linked.txt")
        with self.assertRaisesRegex(WorkspaceError, "Symbolic links"):
            self.workspace.create("linked.txt", "never")
        self.assertEqual(original.read_text("utf-8"), "must remain")

    def test_invalid_restore_key(self):
        for value in ("../other", "abc__", "0" * 24 + "__../secret.txt"):
            with self.assertRaises(WorkspaceError):
                self.workspace.restore(value)


if __name__ == "__main__":
    unittest.main()

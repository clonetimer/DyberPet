"""Save snapshots must be real, verifiable and non-destructive."""
import json
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile
from DyberPet.assistant.save_snapshot import BackupError, create_backup, verify_backup


class SaveSnapshotTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.data = self.root / "data"
        self.data.mkdir()
        (self.data / "settings.json").write_text('{"volume":0.5}', encoding="utf8")
        (self.data / "pet_data.json").write_text('{"Kitty":{"HP":80}}', encoding="utf8")
        (self.data / "task_data.json").write_text('{"tasks":[]}', encoding="utf8")
        self.target = self.root / "backup.zip"

    def test_backup_roundtrip_checksums_and_names(self):
        result = create_backup(self.data, self.target)
        self.assertEqual(result, verify_backup(self.target))
        self.assertEqual(result["files"], ["settings.json", "pet_data.json", "task_data.json"])
        with ZipFile(self.target) as z:
            self.assertEqual(json.loads(z.read("data/pet_data.json"))["Kitty"]["HP"], 80)
            self.assertNotIn(str(self.data), z.read("manifest.json").decode())

    def test_never_overwrite(self):
        self.target.write_bytes(b"original")
        with self.assertRaises(FileExistsError):
            create_backup(self.data, self.target)
        self.assertEqual(self.target.read_bytes(), b"original")

    def test_missing_save_fails_without_output(self):
        (self.data / "pet_data.json").unlink()
        with self.assertRaises(BackupError):
            create_backup(self.data, self.target)
        self.assertFalse(self.target.exists())

    def test_detect_tampering(self):
        create_backup(self.data, self.target)
        with ZipFile(self.target) as z:
            data = {name: z.read(name) for name in z.namelist()}
        with ZipFile(self.target, "w") as z:
            for name, value in data.items():
                z.writestr(name, b"changed" if name == "data/pet_data.json" else value)
        with self.assertRaises(BackupError):
            verify_backup(self.target)

    def test_reject_zip_traversal(self):
        with ZipFile(self.target, "w") as z:
            z.writestr("manifest.json", '{"format":"dyberpet-data-v1","files":[]}')
            z.writestr("../untrusted", "content")
        with self.assertRaises(BackupError):
            verify_backup(self.target)

    def test_reject_source_symlink(self):
        try:
            (self.data / "version").symlink_to(self.data / "settings.json")
        except (OSError, NotImplementedError):
            self.skipTest("Symlinks unavailable")
        with self.assertRaises(BackupError):
            create_backup(self.data, self.target)


if __name__ == "__main__":
    unittest.main()

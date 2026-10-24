"""Transactional offline restore must preserve user data on every failure."""
import json
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from DyberPet.assistant.save_snapshot import BackupError, create_backup
from DyberPet.assistant.offline_restore import (
    JOURNAL, STAGE_PREFIX, PREFIX, recover_interrupted_restore, restore_backup,
)


class OfflineRestoreTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.data = self.base / "data"
        self.data.mkdir()
        self._write_valid(self.data, volume=0.2, pet=80)
        self.original = self.base / "original.zip"
        create_backup(self.data, self.original)
        self.new_data = self.base / "new-data"
        self.new_data.mkdir()
        self._write_valid(self.new_data, volume=0.8, pet=40)
        self.updated = self.base / "updated.zip"
        create_backup(self.new_data, self.updated)

    def _write_valid(self, folder, *, volume, pet):
        (folder / "settings.json").write_text(
            json.dumps({"default_pet":"Kitty","volume":volume}), encoding="utf-8")
        (folder / "pet_data.json").write_text(
            json.dumps({"Kitty":{"HP":pet,"HP_tier":3,"FV":5,"FV_lvl":0}}),
            encoding="utf-8")
        (folder / "task_data.json").write_text('{"history":[]}', encoding="utf-8")

    def _hp(self):
        return json.loads((self.data / "pet_data.json").read_text())["Kitty"]["HP"]

    def test_commit_has_old_directory_and_independent_sha_zip(self):
        (self.data / "personal_note.txt").write_text("keep original only")
        result = restore_backup(self.updated, self.data)
        self.assertTrue(result["ok"])
        self.assertEqual(self._hp(), 40)
        previous = Path(result["pre_restore_directory"])
        self.assertEqual((previous / "personal_note.txt").read_text(), "keep original only")
        self.assertEqual(json.loads((previous / "pet_data.json").read_text())["Kitty"]["HP"], 80)
        with ZipFile(result["pre_restore_archive"]) as z:
            self.assertEqual(json.loads(z.read("data/settings.json"))["volume"], 0.2)
        self.assertFalse((self.base / JOURNAL).exists())
        self.assertFalse(any(self.base.glob(STAGE_PREFIX + "*")))

    def test_invalid_archive_checksum_never_changes_live_data(self):
        with ZipFile(self.updated) as z:
            rows = {name:z.read(name) for name in z.namelist()}
        with ZipFile(self.updated, "w") as z:
            for name, content in rows.items():
                z.writestr(name, b"altered" if name == "data/pet_data.json" else content)
        with self.assertRaises(BackupError):
            restore_backup(self.updated, self.data)
        self.assertEqual(self._hp(), 80)
        self.assertFalse((self.base / JOURNAL).exists())

    def test_valid_checksum_but_invalid_pet_json_structure_rejected(self):
        (self.new_data / "pet_data.json").write_text('{"Kitty":{"HP":"bad"}}')
        malformed = self.base / "malformed.zip"
        create_backup(self.new_data, malformed)
        with self.assertRaises(BackupError):
            restore_backup(malformed, self.data)
        self.assertEqual(self._hp(), 80)

    def test_failure_after_rename_rolls_back(self):
        def fail():
            raise OSError("injected filesystem move fault")
        with self.assertRaises(OSError):
            restore_backup(self.updated, self.data, failure_hook=fail)
        self.assertEqual(self._hp(), 80)
        self.assertFalse((self.base / JOURNAL).exists())
        self.assertFalse(any(self.base.glob(STAGE_PREFIX + "*")))

    def test_crash_journal_missing_active_data_recovers_original(self):
        identifier = "a"*32
        previous = self.base / (PREFIX+identifier)
        stage = self.base / (STAGE_PREFIX+identifier)
        stage.mkdir()
        (stage / "test").write_text("staged")
        self.data.rename(previous)
        (self.base / JOURNAL).write_text(json.dumps({
            "format":"dyberpet-offline-restore-v1",
            "previous":previous.name, "stage":stage.name,
        }))
        self.assertEqual(recover_interrupted_restore(self.data),
                         "rolled-back-interrupted-restore")
        self.assertEqual(self._hp(), 80)
        self.assertFalse((self.base / JOURNAL).exists())

    def test_existing_data_is_never_overwritten_by_recovery(self):
        identifier = "b"*32
        previous = self.base / (PREFIX+identifier)
        previous.mkdir()
        (previous / "pet_data.json").write_text('{"old":"backup"}')
        (self.base / JOURNAL).write_text(json.dumps({
            "format":"dyberpet-offline-restore-v1",
            "previous":previous.name, "stage":STAGE_PREFIX+identifier,
        }))
        self.assertEqual(recover_interrupted_restore(self.data), "already-has-data")
        self.assertEqual(self._hp(), 80)
        self.assertTrue(previous.exists())

    def test_bad_journal_rejected_no_untrusted_rename(self):
        (self.base / JOURNAL).write_text(json.dumps({
            "format":"dyberpet-offline-restore-v1",
            "previous":"../../outside", "stage":STAGE_PREFIX+"c"*32
        }))
        with self.assertRaises(BackupError):
            recover_interrupted_restore(self.data)
        self.assertEqual(self._hp(), 80)

    def test_missing_current_save_blocks_without_modification(self):
        (self.data / "pet_data.json").unlink()
        with self.assertRaises(BackupError):
            restore_backup(self.updated, self.data)
        self.assertFalse((self.base / JOURNAL).exists())

    def test_refuses_symlink_data_dir(self):
        linked = self.base / "external"
        linked.mkdir()
        path = linked / "data"
        try:
            path.symlink_to(self.data, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks unavailable")
        with self.assertRaises(BackupError):
            restore_backup(self.updated, path)


if __name__ == "__main__":
    unittest.main()

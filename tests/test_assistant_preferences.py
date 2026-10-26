"""Assistant configuration persistence and user-controlled folder delegation."""
import json
import tempfile
import unittest
from pathlib import Path

from DyberPet.assistant.preferences import defaults, load, save, validate
from DyberPet.assistant.files import (
    PetWorkspace, WorkspaceError, validate_session_folder
)


class AssistantPreferencesTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.file = self.root / "settings" / "assistant.json"

    def test_defaults_and_atomic_roundtrip(self):
        self.assertFalse(load(self.file)["auto_speak"])
        self.assertFalse(load(self.file)["ppl_enabled"])
        prefs = defaults()
        prefs["personas"] = {"咕嘎": "guga", "Doro": "doro"}
        prefs["llm_model"] = "loaded-qwen"
        prefs["bubble_enabled"] = False
        save(prefs, self.file)
        self.assertEqual(load(self.file), prefs)
        self.assertEqual(list(self.file.parent.glob("*.tmp")), [])

    def test_per_role_favorite_categories_are_validated_and_saved(self):
        prefs = defaults()
        prefs["interaction_favorites"] = {"咕嘎": "greet", "Doro": "jump"}
        save(prefs, self.file)
        self.assertEqual(load(self.file)["interaction_favorites"], prefs["interaction_favorites"])
        for bad in ({"../Other": "jump"}, {"Doro": "madeup"},
                    {"Doro": None}, {"Doro": ["greet"]}, {"Doro": {}}):
            raw = defaults()
            raw["interaction_favorites"] = bad
            with self.assertRaises(ValueError):
                validate(raw)
        self.assertEqual(load(self.file), prefs)

    def test_reject_external_endpoint_and_never_replace_valid_file(self):
        initial = defaults()
        save(initial, self.file)
        evil = defaults()
        evil["llm_url"] = "http://evil.example:8000"
        with self.assertRaises(ValueError):
            save(evil, self.file)
        self.assertEqual(load(self.file), initial)

    def test_bad_persona_schema_rejected(self):
        raw = defaults()
        raw["personas"]["Doro"] = "unknown_character"
        with self.assertRaises(ValueError):
            validate(raw)
        raw["personas"] = {"Doro": "doro"}
        raw["auto_speak"] = 1
        with self.assertRaises(ValueError):
            validate(raw)

    def test_unrecognized_sensitive_fields_not_persisted(self):
        raw = defaults()
        raw.update({"chat_log": "private", "transcript": "secret",
                    "ppl_snapshot": "private rendered text"})
        save(raw, self.file)
        payload = self.file.read_text("utf-8")
        self.assertNotIn("secret", payload)
        self.assertNotIn("rendered text", payload)
        self.assertNotIn("chat_log", payload)

    def test_corrupt_file_reports_instead_of_overwriting(self):
        self.file.parent.mkdir(parents=True)
        self.file.write_text("{corrupt", encoding="utf-8")
        with self.assertRaises(ValueError):
            load(self.file)
        self.assertEqual(self.file.read_text("utf-8"), "{corrupt")


class SessionFolderTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name) / "FakeHome"
        self.home.mkdir()
        self.target = self.home / "Documents" / "PetNotes"
        self.target.mkdir(parents=True)

    def test_only_nested_explicit_personal_directory(self):
        target = validate_session_folder(self.target, home=self.home)
        self.assertEqual(target, self.target.resolve())
        with self.assertRaises(WorkspaceError):
            validate_session_folder(self.home, home=self.home)
        with self.assertRaises(WorkspaceError):
            validate_session_folder(self.target.parent, home=self.home)
        with self.assertRaises(WorkspaceError):
            validate_session_folder(self.home.parent, home=self.home)

    def test_reject_hidden_and_suspicious_folders(self):
        hidden = self.home / ".ssh" / "notes"
        hidden.mkdir(parents=True)
        with self.assertRaises(WorkspaceError):
            validate_session_folder(hidden, home=self.home)
        appdata = self.home / "AppData" / "something"
        appdata.mkdir(parents=True)
        with self.assertRaises(WorkspaceError):
            validate_session_folder(appdata, home=self.home)

    def test_reject_symlink_indirection(self):
        private = self.home.parent / "other"
        private.mkdir()
        alias = self.home / "Documents" / "Linked"
        try:
            alias.symlink_to(private, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("Symlinks unavailable")
        with self.assertRaises(WorkspaceError):
            validate_session_folder(alias, home=self.home)

    def test_user_workspace_does_not_allow_recursive_changes(self):
        root = validate_session_folder(self.target, home=self.home)
        pet = PetWorkspace(root)
        pet.create("a.txt", "hello")
        nested = root / "Nested"
        nested.mkdir()
        (nested / "other.txt").write_text("untouched")
        self.assertEqual(pet.list_files(), ["a.txt"])
        with self.assertRaises(WorkspaceError):
            pet.soft_delete("Nested/other.txt")
        self.assertEqual((nested / "other.txt").read_text(), "untouched")


if __name__ == "__main__":
    unittest.main()

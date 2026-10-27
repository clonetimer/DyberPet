"""R17: newly installed real creator sprites need a complete runtime restart."""
from __future__ import annotations

from types import SimpleNamespace
import unittest

from tools.creator_launch_choice import (
    verified_new_artist_folders, stage_default_pet)


def sample_installation():
    return {"results": [
        {"profile": "genshin_nahida", "status": "installed_unreviewed",
         "verified_native_folders": ["SourceNahida", "ForgedFolder"]},
        {"profile": "genshin_xiao", "status": "failed",
         "verified_native_folders": ["SourceXiao"]},
        {"profile": "genshin_klee", "status": "installed_unreviewed",
         "verified_native_folders": ["DemoKlee"]},
        {"profile": "genshin_venti", "status": "installed_unreviewed",
         "verified_native_folders": ["../unsafe", "SourceNahida"]},
    ]}


def sample_inventory():
    return {"characters": [
        {"profile": "genshin_nahida", "installed_folders": [
            {"folder": "SourceNahida", "is_original_demo": False},
            {"folder": "ForgedFolder", "is_original_demo": True}]},
        {"profile": "genshin_xiao", "installed_folders": [
            {"folder": "SourceXiao", "is_original_demo": False}]},
        {"profile": "genshin_klee", "installed_folders": [
            {"folder": "DemoKlee", "is_original_demo": True}]},
        {"profile": "genshin_venti", "installed_folders": [
            {"folder": "SourceVenti", "is_original_demo": False}]},
    ]}


class NextStartSelectionTests(unittest.TestCase):
    def test_only_receipt_and_fresh_identity_matched_native_folder(self):
        options = verified_new_artist_folders(
            sample_installation(), sample_inventory())
        self.assertEqual(options,
                         {"genshin_nahida · SourceNahida": "SourceNahida"})

    def test_missing_malformed_or_demo_inventory_does_not_offer_launch(self):
        self.assertEqual(verified_new_artist_folders(
            {"results": []}, sample_inventory()), {})
        for invalid in ({}, {"results": "fake"}):
            with self.assertRaisesRegex(ValueError, "native creator results"):
                verified_new_artist_folders(invalid, sample_inventory())

    def test_default_changes_only_for_verified_option(self):
        saved = []
        state = SimpleNamespace(
            default_pet="Kitty",
            save_settings=lambda: saved.append("saved"))
        with self.assertRaisesRegex(ValueError, "approved"):
            stage_default_pet(state, "SourceXiao", ["SourceNahida"])
        self.assertEqual(state.default_pet, "Kitty")
        self.assertFalse(saved)
        self.assertEqual(stage_default_pet(
            state, "SourceNahida", ["SourceNahida"]), "SourceNahida")
        self.assertEqual(state.default_pet, "SourceNahida")
        self.assertEqual(saved, ["saved"])

    def test_failed_save_restores_current_default_and_never_launches(self):
        def fail_save():
            raise OSError("settings directory is read only")
        state = SimpleNamespace(default_pet="Kitty",
                                save_settings=fail_save)
        with self.assertRaises(OSError):
            stage_default_pet(state, "SourceNahida", ["SourceNahida"])
        self.assertEqual(state.default_pet, "Kitty")


if __name__ == "__main__":
    unittest.main()

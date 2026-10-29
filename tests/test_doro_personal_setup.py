"""Personal-only Doro installer tests: synthetic source ZIPs, zero artist art."""
from __future__ import annotations

import io
import json
import os
from pathlib import Path
import tempfile
import unittest
import zipfile

from tools.doro_personal_setup import (
    find_doro_archives, find_doro_archives_in_directories, setup_personal_doro_zip,
)


class PersonalDoroSetupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.downloads = self.base / "Downloads"
        self.downloads.mkdir()
        self.private = self.base / "AppData" / "Local" / "DyberPet" / "PersonalDoro"
        self.zip = self.downloads / "Dororong_Meme_Live2D_Model_By_0x4682B4.zip"
        self.manifest = {
            "Version": 3,
            "FileReferences": {
                "Moc": "Doro.moc3",
                "Textures": ["texture.png"],
                "Expressions": [{"Name": "Amaze", "File": "Amaze.exp3.json"}],
                "Motions": {}
            },
            "HitAreas": [{"Name": "HitAreaFace", "Id": "Face"}]
        }
        self.files = {
            "OriginalDoro/Doro/Doro.model3.json": json.dumps(self.manifest),
            "OriginalDoro/Doro/Doro.moc3": b"TEST_NOT_REAL_MOC3",
            "OriginalDoro/Doro/texture.png": b"TEST_NOT_REAL_PNG",
            "OriginalDoro/Doro/Amaze.exp3.json": "{}",
            "OriginalDoro/Doro/Doro.vtube.json": json.dumps({
                "FileReferences": {
                    "Model": "Doro.model3.json", "IdleAnimation": "Idle.motion3.json"}}),
            "OriginalDoro/Doro/Idle.motion3.json": "{}",
            "OriginalDoro/readme.txt": "Fixture only - not real art",
        }
        self.make_archive()

    def make_archive(self):
        with zipfile.ZipFile(self.zip, "w", zipfile.ZIP_DEFLATED) as arc:
            for name, data in self.files.items():
                arc.writestr(name, data)

    def test_auto_detect_and_install_original_art_byte_identical(self):
        self.assertEqual(find_doro_archives(self.downloads), [self.zip])
        before = self.zip.read_bytes()
        selected = setup_personal_doro_zip(self.zip, self.private)
        self.assertEqual(selected.name, "Doro.model3.json")
        self.assertEqual(selected.parent.parent, self.private)
        self.assertEqual(selected.read_text("utf-8"), json.dumps(self.manifest))
        self.assertEqual((selected.parent / "texture.png").read_bytes(),
                         self.files["OriginalDoro/Doro/texture.png"])
        self.assertTrue((selected.parent / "Idle.motion3.json").exists())
        self.assertEqual(self.zip.read_bytes(), before)
        self.assertFalse(any(p.is_dir() and p.name == "OriginalDoro"
                             for p in self.private.iterdir()))

    def test_second_use_has_no_reinstallation_or_overwrite(self):
        first = setup_personal_doro_zip(self.zip, self.private)
        second = setup_personal_doro_zip(self.zip, self.private)
        self.assertEqual(first, second)
        self.assertEqual(len(list(self.private.iterdir())), 1)

    def test_install_does_not_extract_parent_readme_or_unknown_files(self):
        path = setup_personal_doro_zip(self.zip, self.private)
        self.assertFalse((path.parent / "readme.txt").exists())
        self.assertFalse((path.parent.parent / "readme.txt").exists())

    def test_no_discovery_outside_explicit_download_dir(self):
        (self.base / "DoroOther.zip").write_bytes(self.zip.read_bytes())
        self.assertEqual(find_doro_archives(self.downloads), [self.zip])

    def test_finds_redirected_downloads_and_deduplicates_known_folder(self):
        moved = self.base / "OneDrive" / "Downloads"
        moved.mkdir(parents=True)
        source = moved / self.zip.name
        source.write_bytes(self.zip.read_bytes())
        legacy = find_doro_archives(self.downloads)
        combined = find_doro_archives_in_directories(
            [moved, self.downloads, moved, self.base / "not-exist"])
        self.assertEqual(set(combined), set(legacy + [source]))
        self.assertEqual(len(combined), 2)

    def test_both_downloads_paths_empty_returns_empty(self):
        result = find_doro_archives_in_directories(
            [self.base / "not-exist", None, "", self.base / "also-missing"])
        self.assertEqual(result, [])

    def test_reject_traversal_and_preserve_private_folder(self):
        self.files["OriginalDoro/Doro/../../../escape.png"] = b"BAD"
        self.make_archive()
        with self.assertRaises(ValueError):
            setup_personal_doro_zip(self.zip, self.private)
        self.assertFalse((self.base / "escape.png").exists())
        self.assertEqual(list(self.private.glob("Doro_personal_*")), [])

    def test_reject_windows_case_conflicts(self):
        self.files["OriginalDoro/Doro/TEXTURE.PNG"] = b"duplicate on NTFS"
        self.make_archive()
        with self.assertRaisesRegex(ValueError, "duplicate"):
            setup_personal_doro_zip(self.zip, self.private)

    def test_reject_executable_inside_model_tree(self):
        self.files["OriginalDoro/Doro/malware.exe"] = b"DONT_EXECUTE"
        self.make_archive()
        with self.assertRaisesRegex(ValueError, "non-model"):
            setup_personal_doro_zip(self.zip, self.private)

    def test_reject_wrong_model_resources_atomically(self):
        del self.files["OriginalDoro/Doro/Doro.moc3"]
        self.make_archive()
        with self.assertRaisesRegex(ValueError, "Missing"):
            setup_personal_doro_zip(self.zip, self.private)
        self.assertEqual(list(self.private.glob("Doro_personal_*")), [])
        self.assertEqual(list(self.private.glob(".doro-staging-*")), [])

    def test_reject_more_than_one_model_version_in_same_zip(self):
        self.files["OriginalDoro/Doro/CopyDoro.model3.json"] = json.dumps(self.manifest)
        self.make_archive()
        with self.assertRaisesRegex(ValueError, "exactly one"):
            setup_personal_doro_zip(self.zip, self.private)

    def test_reject_symlink_zip_entry(self):
        import stat
        with zipfile.ZipFile(self.zip, "w", zipfile.ZIP_DEFLATED) as arc:
            for name, data in self.files.items():
                arc.writestr(name, data)
            entry = zipfile.ZipInfo("OriginalDoro/Doro/sneaky.png")
            entry.create_system = 3
            entry.external_attr = (stat.S_IFLNK | 0o777) << 16
            arc.writestr(entry, "../../elsewhere")
        with self.assertRaisesRegex(ValueError, "linked"):
            setup_personal_doro_zip(self.zip, self.private)

    def test_reject_zip_without_artist_model(self):
        self.files["OriginalDoro/Doro/Doro.model3.json"] = "{}"
        self.make_archive()
        with self.assertRaisesRegex(ValueError, "Cubism"):
            setup_personal_doro_zip(self.zip, self.private)

    def test_auto_start_is_explicit_only_and_preserves_old_pet_on_missing_model(self):
        from unittest.mock import patch
        import DyberPet.DyberSettings.doro_live2d_dialog as dialog

        class FakeSettings:
            def __init__(self):
                self.values = {}
            def value(self, key, default=None, type=None):
                return self.values.get(key, default)
            def setValue(self, key, value):
                self.values[key] = value

        cfg = FakeSettings()
        with (patch.object(dialog, "QSettings", return_value=cfg),
              patch.object(dialog, "_resolve_installed_doro") as resolver,
              patch.object(dialog, "open_doro_desktop") as opener,
              patch.object(dialog, "inspect_local_live2d") as inspector):
            self.assertFalse(dialog.launch_personal_doro_at_startup())
            resolver.assert_not_called()
            opener.assert_not_called()
            cfg.values[dialog._AUTOSTART_KEY] = True
            resolver.return_value = ""
            self.assertFalse(dialog.launch_personal_doro_at_startup())
            opener.assert_not_called()
            resolver.return_value = "Doro.model3.json"
            inspector.return_value = {"model_json": "Doro.model3.json"}
            self.assertTrue(dialog.launch_personal_doro_at_startup())
            opener.assert_called_once_with({"model_json": "Doro.model3.json"})
            self.assertEqual(cfg.values[dialog._SETTINGS_KEY], "Doro.model3.json")

    def test_gui_has_visible_autostart_preference_and_main_boot_hook(self):
        dialog = (Path(__file__).resolve().parents[1]
                  / "DyberPet" / "DyberSettings" / "doro_live2d_dialog.py"
                  ).read_text(encoding="utf-8")
        run = (Path(__file__).resolve().parents[1] /
               "run_DyberPet.py").read_text(encoding="utf-8")
        self.assertIn("self.start_with_doro = QCheckBox(", dialog)
        self.assertIn("character/doro_live2d_auto_start", dialog)
        self.assertIn("app.p.hide()", dialog)
        self.assertIn("app.p.show()", dialog)
        self.assertIn("QTimer.singleShot(700, launch_personal_doro_at_startup)", run)
        self.assertIn("if _FIRST_RUN:", run)

    def test_gui_official_creator_link_and_downloads_autodetect_are_wired(self):
        source = (Path(__file__).resolve().parents[1] / "DyberPet" /
                  "DyberSettings" / "doro_live2d_dialog.py").read_text("utf-8")
        self.assertIn("_select_local_doro_model", source)
        self.assertIn("_find_personal_doro_downloads()", source)
        self.assertIn("QStandardPaths.StandardLocation.DownloadLocation", source)
        self.assertIn("setup_personal_doro_zip", source)
        self.assertIn("https://booth.pm/zh-cn/items/5867617", source)
        self.assertIn("QStandardPaths.StandardLocation.AppLocalDataLocation", source)


if __name__ == "__main__":
    unittest.main()

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
    find_doro_archives, setup_personal_doro_zip,
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

    def test_gui_official_creator_link_and_downloads_autodetect_are_wired(self):
        source = (Path(__file__).resolve().parents[1] / "DyberPet" /
                  "DyberSettings" / "doro_live2d_dialog.py").read_text("utf-8")
        self.assertIn("_select_local_doro_model", source)
        self.assertIn("find_doro_archives(Path.home() / \"Downloads\")", source)
        self.assertIn("setup_personal_doro_zip", source)
        self.assertIn("https://booth.pm/zh-cn/items/5867617", source)
        self.assertIn("QStandardPaths.StandardLocation.AppLocalDataLocation", source)


if __name__ == "__main__":
    unittest.main()

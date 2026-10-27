"""Verify locally embedded personal Windows portable archives, entirely offline."""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import zipfile

from tools.local_offline_bundle import create_local_bundle, inspect_local_bundle


def fake_genshin(*_args, **_kwargs):
    return {"summary": {
        "personal_art_profile_count": 2,
        "unmapped_folder_count": 0, "invalid_folder_count": 0,
    }}


def fake_mascot(*_args, **_kwargs):
    return {"summary": {
        "imported_creator_art_count": 1, "invalid_count": 0,
    }}


class LocalOfflineBundleTests(unittest.TestCase):
    def _fixture(self, parent):
        app = parent / "DyberPet"
        roles = app / "res" / "role"
        (roles / "SourceValid").mkdir(parents=True)
        (app / "data").mkdir()
        (app / "DyberPet.exe").write_bytes(b"synthetic standalone app")
        (roles / "SourceValid" / "action.png").write_bytes(b"fake file bytes")
        (app / "data" / "private-tokens.json").write_text('{"token":"PRIVATE"}')
        return app

    def test_confirmed_local_bundle_includes_art_and_excludes_private_data(self):
        with TemporaryDirectory() as td:
            base = Path(td)
            app = self._fixture(base)
            output = base / "DyberPet-Offline-WithRoles.zip"
            with patch("tools.local_offline_bundle.scan_genshin_library", side_effect=fake_genshin), \
                 patch("tools.local_offline_bundle.scan_mascot_library", side_effect=fake_mascot):
                with self.assertRaisesRegex(ValueError, "confirmation"):
                    create_local_bundle(app, output, confirmed=False)
                result = create_local_bundle(app, output, confirmed=True)
            self.assertTrue(output.is_file())
            self.assertGreater(result["size_bytes"], 0)
            self.assertEqual(result["manifest"]["genshin_installed_distinct_profiles"], 2)
            self.assertEqual(result["manifest"]["mascot_creator_art_installed"], 1)
            self.assertFalse(result["manifest"]["genshin_65_source_target_reached"])
            with zipfile.ZipFile(output) as src:
                entries = src.namelist()
                self.assertIn("DyberPet.exe", entries)
                self.assertIn("res/role/SourceValid/action.png", entries)
                self.assertIn("LOCAL_OFFLINE_BUILD.json", entries)
                self.assertNotIn("data/private-tokens.json", entries)
                report = json.loads(src.read("LOCAL_OFFLINE_BUILD.json"))
                self.assertTrue(report["personal_data_dir_excluded"])
                self.assertFalse(report["author_rights_verified_by_tool"])
            with self.assertRaises(FileExistsError):
                create_local_bundle(app, output, confirmed=True)

    def test_reject_output_inside_app_and_symlink(self):
        with TemporaryDirectory() as td:
            base = Path(td)
            app = self._fixture(base)
            with self.assertRaisesRegex(ValueError, "outside"):
                create_local_bundle(app, app / "malicious.zip", confirmed=True)
            link = app / "res" / "role" / "SourceLinked"
            try:
                link.symlink_to(app / "res", target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("No symlink privileges")
            with patch("tools.local_offline_bundle.scan_genshin_library", side_effect=fake_genshin), \
                 patch("tools.local_offline_bundle.scan_mascot_library", side_effect=fake_mascot):
                with self.assertRaisesRegex(ValueError, "linked directory"):
                    create_local_bundle(app, base / "out.zip", confirmed=True)

    def test_empty_source_inventory_not_misreported_as_65_installed(self):
        with TemporaryDirectory() as td:
            app = self._fixture(Path(td))
            with patch("tools.local_offline_bundle.scan_genshin_library",
                       return_value={"summary": {"personal_art_profile_count": 0,
                                                 "unmapped_folder_count": 0,
                                                 "invalid_folder_count": 0}}), \
                 patch("tools.local_offline_bundle.scan_mascot_library",
                       return_value={"summary": {"imported_creator_art_count": 0,
                                                 "invalid_count": 0}}):
                report = inspect_local_bundle(app)
                self.assertFalse(report["genshin_65_source_target_reached"])
                self.assertFalse(report["contains_user_imported_art"])


    def test_refuse_success_zip_with_no_real_artist_material(self):
        with TemporaryDirectory() as td:
            base = Path(td)
            app = self._fixture(base)
            output = base / "misleading-65-roles.zip"
            with patch("tools.local_offline_bundle.scan_genshin_library",
                       return_value={"summary": {
                           "personal_art_profile_count": 0,
                           "unmapped_folder_count": 0,
                           "invalid_folder_count": 0}}), \
                 patch("tools.local_offline_bundle.scan_mascot_library",
                       return_value={"summary": {
                           "imported_creator_art_count": 0,
                           "invalid_count": 0}}):
                with self.assertRaisesRegex(ValueError, "starter-only ZIP"):
                    create_local_bundle(app, output, confirmed=True)
            self.assertFalse(output.exists())
            self.assertFalse((base / "misleading-65-roles.zip.partial").exists())

    def test_refuse_legacy_generated_demo_even_with_real_art(self):
        with TemporaryDirectory() as td:
            base = Path(td)
            app = self._fixture(base)
            marker = app / "res" / "role" / "SourceValid" / "BUILTIN_CHIBI_DEMO.json"
            marker.write_text('{"generator":"old-placeholder"}', encoding="utf-8")
            with patch("tools.local_offline_bundle.scan_genshin_library",
                       side_effect=fake_genshin), \
                 patch("tools.local_offline_bundle.scan_mascot_library",
                       side_effect=fake_mascot):
                with self.assertRaisesRegex(ValueError, "Generated placeholder"):
                    create_local_bundle(app, base / "out.zip", confirmed=True)
            self.assertFalse((base / "out.zip").exists())

    def test_refuse_invalid_role_before_archiving(self):
        with TemporaryDirectory() as td:
            base = Path(td)
            app = self._fixture(base)
            bad_genshin = {"summary": {
                "personal_art_profile_count": 2,
                "unmapped_folder_count": 0,
                "invalid_folder_count": 1}}
            with patch("tools.local_offline_bundle.scan_genshin_library",
                       return_value=bad_genshin), \
                 patch("tools.local_offline_bundle.scan_mascot_library",
                       side_effect=fake_mascot):
                with self.assertRaisesRegex(ValueError, "Invalid local character"):
                    create_local_bundle(app, base / "bad.zip", confirmed=True)
            self.assertFalse((base / "bad.zip").exists())


if __name__ == "__main__":
    unittest.main()

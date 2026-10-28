"""Synthetic portable ZIP regression: never downloads or redistributes art."""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile, ZIP_DEFLATED

from tools.verify_personal_portable import _REQUIRED, verify_portable_zip


class PersonalPortableVerificationTests(unittest.TestCase):
    def make_zip(self, root, *, backend="python", edit=None):
        meta = dict(character_templates=123, pinned_source_characters=66,
                    missing_source_characters=57, variant=backend,
                    prebundled_third_party_art=False, release_is_prerelease=True)
        contents = {path: b"synthetic test entry" for path in _REQUIRED}
        contents["PERSONAL65_BUILD_INFO.json"] = json.dumps(meta).encode()
        contents["Run-DyberPet.cmd"] = ("set DYBERPET_NATIVE_BACKEND=" + backend + "\n" +
            ("set DYBERPET_REQUIRE_RUST=1\n" if backend == "rust" else "")).encode()
        contents["res/role/Kitty/idle.png"] = b"synthetic untrusted bytes"
        if edit:
            edit(contents)
        zip_path = root / "portable.zip"
        with ZipFile(zip_path, "w", ZIP_DEFLATED) as zipped:
            for name, value in contents.items():
                zipped.writestr(name, value)
        return zip_path

    def test_python_and_rust_valid_without_creator_art(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            for backend in ("python", "rust"):
                path = self.make_zip(root, backend=backend)
                receipt = verify_portable_zip(path, backend)
                self.assertEqual(receipt["pinned_source_characters"], 66)
                self.assertFalse(receipt["creator_art_prebundled"])
                self.assertFalse(receipt["real_windows_desktop_qa_verified"])

    def test_reject_wrong_variant(self):
        with TemporaryDirectory() as folder:
            path = self.make_zip(Path(folder), backend="python")
            with self.assertRaisesRegex(ValueError, "backend metadata"):
                verify_portable_zip(path, "rust")

    def test_reject_stale_counts_and_missing_installer(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            def bad_count(data):
                meta = json.loads(data["PERSONAL65_BUILD_INFO.json"])
                meta["pinned_source_characters"] = 65
                data["PERSONAL65_BUILD_INFO.json"] = json.dumps(meta).encode()
            with self.assertRaisesRegex(ValueError, "source counts"):
                verify_portable_zip(self.make_zip(root, edit=bad_count), "python")
            def no_installer(data):
                data.pop("Install-Available-Roles.cmd")
            with self.assertRaisesRegex(ValueError, "Missing required"):
                verify_portable_zip(self.make_zip(root, edit=no_installer), "python")

    def test_reject_embedded_art_and_private_data(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            for name in ("res/role/SourceGenshin/foo.png", "data/private.json",
                         "res/role/Kitty/BUILTIN_CHIBI_DEMO.json",
                         "res/role/Kitty/artist_source_receipt.json",
                         "../escaped.txt"):
                with self.subTest(entry=name):
                    def extra(data):
                        data[name] = b"unwanted"
                    path = self.make_zip(root, edit=extra)
                    with self.assertRaisesRegex(ValueError, "Creator|Private|placeholder|Unsafe"):
                        verify_portable_zip(path, "python")

    def test_reject_duplicate_case_insensitive_names(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            path = self.make_zip(root)
            with ZipFile(path, "a") as archive:
                archive.writestr("run-dyberpet.cmd", b"bad duplicate")
            with self.assertRaisesRegex(ValueError, "Duplicate"):
                verify_portable_zip(path, "python")


if __name__ == "__main__":
    unittest.main()

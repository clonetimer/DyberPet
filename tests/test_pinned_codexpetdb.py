"""Hash-pinned public ZIPs are installable only after exact byte verification."""
from __future__ import annotations

import ast
import copy
import hashlib
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from PIL import Image, ImageDraw

from tools.install_pinned_codexpetdb import (
    get_verified_package, install_pinned_codexpetdb, listed_packages,
    fixed_archive_url, MAX_ARCHIVE_BYTES,
)


def simulated_codex_package(identifier="gi-kaveh", *, incorrect=False):
    picture = Image.new("RGBA", (1536, 1872), (0, 0, 0, 0))
    draw = ImageDraw.Draw(picture)
    for row in range(9):
        for col in range(3):
            x, y = col * 192, row * 208
            draw.rectangle((x + 23, y + 18, x + 96 + col * 7, y + 174),
                           fill=(80 + col * 30, 30 + row * 13, 140, 255))
    atlas = BytesIO()
    picture.save(atlas, format="PNG")
    package = BytesIO()
    with zipfile.ZipFile(package, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("pet.json", json.dumps({
            "id": "gi-kinich" if incorrect else identifier,
            "displayName": "Private test fixture",
            "spriteVersionNumber": 1,
            "spritesheetPath": "spritesheet.png",
        }))
        archive.writestr("spritesheet.png", atlas.getvalue())
        archive.writestr("run-me.bat", "Never run a package executable.")
    return package.getvalue()


class HashPinnedPackageTests(unittest.TestCase):
    def configure(self, package):
        entry = copy.deepcopy(listed_packages())
        rec = entry["sources"]["kaveh"]
        rec["sha256"] = hashlib.sha256(package).hexdigest()
        rec["verified_bytes"] = len(package)
        rec["max_bytes"] = MAX_ARCHIVE_BYTES
        return entry

    def test_exact_public_listing_sources_are_unique(self):
        manifest = listed_packages()
        self.assertEqual(len(manifest["sources"]), 20)
        self.assertEqual(set(manifest["sources"]),
                         {"kaveh", "kinich", "kirara", "alhaitham", "baizhu", "candace", "chevreuse", "layla", "chiori", "cyno", "dehya", "freminet", "charlotte", "columbina", "gaming", "iansan", "aino", "dahlia", "flins", "lan_yan"})
        for key, record in manifest["sources"].items():
            self.assertEqual(len(record["sha256"]), 64)
            self.assertGreater(record["verified_bytes"], 100)
            url = fixed_archive_url(record)
            self.assertTrue(url.startswith("https://cdn.codexpetdb.com/revisions/"))
            self.assertTrue(url.endswith("/" + record["slug"] + ".zip"))
            self.assertTrue(record["profile"].startswith("genshin_"))

    def test_verified_zip_is_installed_atomically_without_executing_script(self):
        package = simulated_codex_package()
        listing = self.configure(package)
        observed = []
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "roles"

            def fake_download(url, max_bytes):
                observed.append((url, max_bytes))
                return package

            with self.assertRaisesRegex(ValueError, "Confirm personal opt-in"):
                install_pinned_codexpetdb(
                    "kaveh", root, confirmed=False,
                    downloader=fake_download, manifest=listing)
            self.assertEqual(observed, [])
            first = install_pinned_codexpetdb(
                "kaveh", root, confirmed=True, downloader=fake_download,
                manifest=listing)
            self.assertTrue(first.is_dir())
            self.assertTrue(observed[0][0].endswith("/gi-kaveh.zip"))
            self.assertFalse((first / "run-me.bat").exists())
            receipt = json.loads((first / "PERSONAL_IMPORT.json").read_text("utf-8"))
            self.assertEqual(receipt["source_zip_sha256_verified"],
                             listing["sources"]["kaveh"]["sha256"])
            self.assertEqual(receipt["selected_profile"], "genshin_kaveh")
            self.assertFalse(receipt["character_original_likeness_qa_passed"])
            self.assertFalse(receipt["redistribution_allowed_by_tool"])
            self.assertTrue((first / "ACTION_PIXEL_AUDIT.json").exists())
            qa = json.loads((first / "ACTION_PIXEL_AUDIT.json").read_text("utf-8"))
            self.assertGreaterEqual(qa["summary"]["native_actions"], 5)
            self.assertFalse(qa["summary"]["character_visual_likeness_verified"])
            second = install_pinned_codexpetdb(
                "kaveh", root, confirmed=True, downloader=fake_download,
                manifest=listing)
            self.assertNotEqual(first, second)
            self.assertTrue(first.exists())

    def test_bad_hash_or_unsupported_source_never_creates_role(self):
        package = simulated_codex_package()
        listing = self.configure(package)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "roles"
            bad = package[:-1] + bytes([package[-1] ^ 1])  # same length, altered SHA
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                install_pinned_codexpetdb(
                    "kaveh", root, confirmed=True, manifest=listing,
                    downloader=lambda url, size: bad)
            self.assertFalse(root.exists())
            with self.assertRaisesRegex(ValueError, "Unregistered"):
                get_verified_package(
                    "unlisted", downloader=lambda url, size: package,
                    manifest=listing)

    def test_wrong_character_id_and_failed_review_leave_no_partial_install(self):
        for wrong_identity, failed_review in ((True, False), (False, True)):
            package = simulated_codex_package(incorrect=wrong_identity)
            listing = self.configure(package)
            with tempfile.TemporaryDirectory() as td:
                root = Path(td) / "roles"
                if failed_review:
                    with patch("tools.install_pinned_codexpetdb.audit_native_character",
                               side_effect=RuntimeError("failed QA")):
                        with self.assertRaisesRegex(RuntimeError, "failed QA"):
                            install_pinned_codexpetdb(
                                "kaveh", root, confirmed=True, manifest=listing,
                                downloader=lambda url, size: package)
                else:
                    with self.assertRaisesRegex(ValueError, "pet.json.id"):
                        install_pinned_codexpetdb(
                            "kaveh", root, confirmed=True, manifest=listing,
                            downloader=lambda url, size: package)
                self.assertTrue(root.is_dir())
                self.assertEqual(list(root.iterdir()), [])

    def test_gui_only_downloads_after_yes_and_uses_worker(self):
        path = Path(__file__).resolve().parents[1] / "DyberPet/DyberSettings/CharCardUI.py"
        source = path.read_text("utf-8")
        ast.parse(source)
        self.assertIn("个人使用：下载 SHA-256 固定的十六位原神角色原画 ZIP", source)
        self.assertIn('"pinned_codexpetdb_local" if local_archive else "pinned_codexpetdb"', source)
        self.assertIn('elif self.mode in ("pinned_codexpetdb", "pinned_codexpetdb_local"):', source)
        self.assertIn("QMessageBox.StandardButton.Yes", source)


if __name__ == "__main__":
    unittest.main()

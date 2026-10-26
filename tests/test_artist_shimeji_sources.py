"""All 123 entries must report truthful creator-source coverage.

Tests use local fake PNG bytes; no unaudited public art is bundled or fetched
during CI. Real network downloads and Windows visual acceptance remain separate.
"""
from __future__ import annotations

import hashlib
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image

from tools.artist_visual_review import create_native_art_review
from tools.character_source_coverage import source_coverage
from tools.install_artist_shimeji import (
    _download_png, install_artist_shimeji, source_manifest)
from tools.install_native_role import validate_native_role


class CreatorSourcesTests(unittest.TestCase):
    def test_123_templates_and_all_discovered_sources(self):
        r = source_coverage()
        s = r["summary"]
        self.assertEqual(s["template_count"], 123)
        self.assertEqual(s["pinned_source_options"], 84)
        self.assertEqual(s["characters_with_pinned_sources"], 61)
        self.assertEqual(s["characters_without_pinned_sources"], 62)
        self.assertEqual(s["verified_likeness_count"], 0)
        self.assertEqual(s["physical_windows_qa_count"], 0)
        by_id = {c["id"]: c for c in r["characters"]}
        for profile in ("genshin_albedo", "genshin_chongyun", "genshin_kazuha",
                        "genshin_venti", "genshin_thoma", "genshin_citlali"):
            self.assertTrue(by_id[profile]["source_found"])
        for item in r["characters"]:
            self.assertFalse(item["installed"])
            self.assertFalse(item["visual_likeness_qa_passed"])
            self.assertFalse(item["rights_verified"])
            for x in item["source_candidates"]:
                if x["provider"] == "codexpetdb_zip":
                    self.assertTrue(x["url"].startswith(
                        "https://cdn.codexpetdb.com/revisions/"))
                    self.assertEqual(len(x["archive_sha256"]), 64)
                    self.assertTrue(x["byte_integrity_tested_in_ci"])
                    self.assertFalse(x["artist_character_likeness_verified"])
                else:
                    self.assertTrue(x["url"].startswith("https://github.com/"))
                self.assertFalse(x["asset_is_bundled"])

    def test_all_eight_shimeji_roles_have_immutable_frame_pins(self):
        manifest = source_manifest()
        self.assertEqual(len(manifest["roles"]), 8)
        self.assertEqual(len(manifest["revision"]), 40)
        total = 0
        for key, role in manifest["roles"].items():
            self.assertGreaterEqual(len(role["files"]), 12, key)
            for name, spec in role["files"].items():
                self.assertEqual(len(spec["sha"]), 40, name)
                self.assertGreater(spec["size"], 100, name)
                total += 1
        self.assertEqual(total, 228)

    @staticmethod
    def png():
        stream = BytesIO()
        Image.new("RGBA", (32, 48), (80, 180, 90, 220)).save(stream, format="PNG")
        return stream.getvalue()

    def test_download_rejects_tamper_and_mismatched_length(self):
        png = self.png()
        sha = hashlib.sha1(b"blob " + str(len(png)).encode() + b"\0" + png).hexdigest()
        def opener(req, timeout):
            self.assertIn("raw.githubusercontent.com", req.full_url)
            return BytesIO(png)
        self.assertEqual(_download_png("https://raw.githubusercontent.com/example", 
                                       {"size": len(png), "sha": sha}, opener=opener), png)
        with self.assertRaises(ValueError):
            _download_png("https://raw.githubusercontent.com/example", 
                          {"size": len(png), "sha": "0"*40}, opener=opener)
        with self.assertRaises(ValueError):
            _download_png("https://raw.githubusercontent.com/example", 
                          {"size": len(png) + 1, "sha": sha}, opener=opener)

    def test_offline_native_install_preserves_original_png_bytes(self):
        png = self.png()
        sha = hashlib.sha1(b"blob " + str(len(png)).encode() + b"\0" + png).hexdigest()
        keys = ("id1_1.png", "walk1.png", "drag1.png", "fall1.png", "sp1_1.png")
        spec = {"size": len(png), "sha": sha}
        sample = {"repository": "AkshitIreddy/AI-Desktop-Pet",
                  "revision": "a"*40, "roles": {
                      "albedo": {"name": "阿贝多", "profile": "genshin_albedo",
                                 "files": {key: spec for key in keys}}}}
        calls = []
        def fake_download(url, expected):
            calls.append(url)
            self.assertEqual(expected, spec)
            return png
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaises(ValueError):
                install_artist_shimeji("albedo", root, manifest=sample,
                                       downloader=fake_download)
            self.assertEqual(calls, [])
            result = install_artist_shimeji("albedo", root, manifest=sample,
                                            downloader=fake_download, confirmed=True)
            folder = root / result["folder"]
            self.assertTrue(folder.is_dir())
            self.assertEqual((folder / "action" / "stand_0.png").read_bytes(), png)
            self.assertEqual((folder / "action" / "walk_0.png").read_bytes(), png)
            self.assertTrue((folder / "ANIMATION_PREVIEW.png").is_file())
            self.assertGreaterEqual(validate_native_role(folder)["actions"], 5)
            receipt = json.loads((folder / "PERSONAL_IMPORT.json").read_text("utf-8"))
            self.assertTrue(receipt["verified_exact_source_frame_bytes"])
            self.assertFalse(receipt["likeness_manually_reviewed"])
            self.assertFalse(receipt["source_rights_verified"])
            with self.assertRaises(FileExistsError):
                install_artist_shimeji("albedo", root, manifest=sample,
                                       downloader=fake_download, confirmed=True)
            self.assertTrue(folder.is_dir())


if __name__ == "__main__":
    unittest.main()

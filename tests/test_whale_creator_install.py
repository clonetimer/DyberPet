"""Whale local importer regression: synthetic byte fixtures, no upstream media."""
from __future__ import annotations
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from tools.install_whale_pet import (
    CORE_ACTIONS, SOURCE_REV, _git_blob_sha, fetch_pinned_video,
    install_whale_pet, select_actions, source_catalog, write_native_configs,
)
from tools.install_native_role import validate_native_role


class DownloadResponse(io.BytesIO):
    def __init__(self, data, url):
        super().__init__(data)
        self.url = url

    def geturl(self):
        return self.url


class WhaleImporterTests(unittest.TestCase):
    def test_catalog_has_95_pinned_webm_assets_and_core_has_16(self):
        catalog = source_catalog()
        self.assertEqual(catalog["source_commit"], SOURCE_REV)
        self.assertEqual(len(select_actions(catalog, "full")), 95)
        core = select_actions(catalog, "core")
        self.assertEqual(len(core), len(CORE_ACTIONS))
        self.assertEqual(len({r["path"] for r in core}), len(core))

    def test_git_blob_identity_and_redirect_checks(self):
        data = b"sample upstream animation bytes"
        row = {"path": "assets/thumb/idle/breathing.webm",
               "size": len(data), "git_blob_sha1": _git_blob_sha(data)}
        def good(url, timeout):
            self.assertEqual(timeout, 30)
            self.assertIn(SOURCE_REV, url)
            return DownloadResponse(data, url)
        self.assertEqual(fetch_pinned_video(row, opener=good), data)
        changed = {**row, "git_blob_sha1": "0" * 40}
        with self.assertRaisesRegex(ValueError, "differ"):
            fetch_pinned_video(changed, opener=good)
        def bad_redirect(url, timeout):
            return DownloadResponse(data, "https://other.example/modified.webm")
        with self.assertRaisesRegex(ValueError, "redirect"):
            fetch_pinned_video(row, opener=bad_redirect)

    def test_opt_in_and_failure_do_not_create_partial_role(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "role"
            with self.assertRaisesRegex(ValueError, "acknowledgement"):
                install_whale_pet(root)
            self.assertFalse(root.exists())
            exe = Path(td) / "fake-ffmpeg.exe"
            exe.write_bytes(b"stub")
            def fail_fetch(*args, **kwargs):
                raise ValueError("Network offline")
            with patch("tools.install_whale_pet.fetch_pinned_video", fail_fetch):
                with self.assertRaisesRegex(ValueError, "Network offline"):
                    install_whale_pet(root, confirmed=True, ffmpeg=str(exe))
            self.assertEqual(list(root.iterdir()), [])

    def test_core_native_install_then_preserves_old_role(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "role"
            exe = Path(td) / "fake-ffmpeg.exe"
            exe.write_bytes(b"stub")
            def fake_fetch(row, **kwargs):
                return b"synthetic"
            def fake_decode(clip, output, *, ffmpeg, fps):
                output.mkdir(parents=True)
                for index in range(3):
                    img = Image.new("RGBA", (320, 180), (0, 0, 0, 0))
                    for x in range(80, 110):
                        for y in range(65, 105):
                            img.putpixel((x, y), (50 + index, 120, 230, 255))
                    img.save(output / f"frame_{index}.png")
                return 3
            with patch("tools.install_whale_pet.fetch_pinned_video", side_effect=fake_fetch):
                first = install_whale_pet(root, confirmed=True, ffmpeg=str(exe), decoder=fake_decode)
                role1 = root / first["folder"]
                self.assertEqual(first["actions"], 16)
                self.assertEqual(first["frames"], 48)
                self.assertEqual(validate_native_role(role1)["actions"], 16)
                self.assertFalse((role1 / "SOURCE_LICENSE.txt").is_symlink())
                self.assertIn("non-commercial", (role1 / "SOURCE_LICENSE.txt").read_text("utf-8"))
                second = install_whale_pet(root, confirmed=True, ffmpeg=str(exe), decoder=fake_decode)
            self.assertNotEqual(first["folder"], second["folder"])
            self.assertTrue(role1.is_dir())
            self.assertEqual(len(list(root.glob("SourceWhalePet*"))), 2)
            self.assertEqual(json.loads((role1 / "PERSONAL_IMPORT.json").read_text("utf-8"))["selection"], "core")

    def test_native_action_mappings_are_all_defined(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            assets = root / "action"
            assets.mkdir()
            core = select_actions(source_catalog(), "core")
            count = {}
            for action in core:
                name = Path(action["path"]).stem
                count[name] = 2
                for index in range(2):
                    Image.new("RGBA", (320, 180), (255, 0, 0, 60)).save(
                        assets / f"{name}_{index}.png")
            write_native_configs(root, core, count, fps=8)
            self.assertEqual(validate_native_role(root)["actions"], 16)


if __name__ == "__main__":
    unittest.main()

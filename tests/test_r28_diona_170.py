"""R28 Diona original 170-frame importer: strict identity, no synthetic art fallback."""
from __future__ import annotations
import copy
import io
import json
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from PIL import Image

from tools.install_gmcy_diona import (
    SOURCE_KEY, source_manifest, verify_original_frames,
    install_gmcy_diona, source_zip_url, _git_blob_sha,
)
from tools.install_native_role import validate_native_role


def synthetic_archive():
    """Small artificial TEST FIXTURE ONLY, never bundled or treated as author art."""
    manifest = copy.deepcopy(source_manifest())
    contents = []
    for n in range(1, 171):
        img = Image.new("RGBA", (18, 18), ((n*17)%255, (n*29)%255, (n*37)%255, 255))
        dst = io.BytesIO()
        img.save(dst, format="PNG")
        raw = dst.getvalue()
        manifest["files"][n-1] = {
            "num": n, "bytes": len(raw),
            "git_blob_sha1": _git_blob_sha(raw),
        }
        contents.append(raw)
    manifest["original_image_bytes"] = sum(len(x) for x in contents)
    root = f"DesktopPet-Simple-{manifest['commit']}/resources/pet_2/"
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as pack:
        for n, raw in enumerate(contents, 1):
            pack.writestr(root+f"shime{n}.png", raw)
        # Never execute unrelated upstream code, even if it is in the archive.
        pack.writestr(f"DesktopPet-Simple-{manifest['commit']}/main.py",
                      "raise RuntimeError('NEVER EXECUTE SOURCE')")
    return manifest, output.getvalue()


class GmcyDionaImporterTests(unittest.TestCase):
    def test_exact_author_manifest_and_nine_real_source_action_groups(self):
        obj = source_manifest()
        self.assertEqual(obj["chinese_name"], "迪奥娜")
        self.assertEqual(obj["source_profile"], "genshin_diona")
        self.assertEqual(len(obj["files"]), 170)
        self.assertEqual(len(obj["original_action_groups"]), 9)
        self.assertEqual(sum(len(x["frames"]) for x in obj["original_action_groups"]), 170)
        self.assertTrue(source_zip_url().startswith(
            "https://codeload.github.com/GMCY2020/DesktopPet-Simple/zip/"))

    def test_local_zip_exact_sha_and_native_install_without_execution(self):
        manifest, archive = synthetic_archive()
        with tempfile.TemporaryDirectory() as tmp, \
                patch("tools.install_gmcy_diona.source_manifest", return_value=manifest):
            root = Path(tmp) / "role"
            with self.assertRaisesRegex(ValueError, "Explicit personal"):
                install_gmcy_diona(SOURCE_KEY, root, archive_bytes=archive)
            self.assertFalse(root.exists())
            frames = verify_original_frames(archive, manifest=manifest)
            self.assertEqual(len(frames), 170)
            installed = install_gmcy_diona(
                SOURCE_KEY, root, confirmed=True, archive_bytes=archive)
            report = validate_native_role(installed)
            self.assertEqual(report["actions"], 9)
            self.assertEqual(report["images"], 170)
            receipt = json.loads((installed/"PERSONAL_IMPORT.json").read_text("utf-8"))
            self.assertEqual(receipt["selected_profile"], "genshin_diona")
            self.assertTrue(receipt["sha1_blob_sha_verified_for_every_frame"])
            self.assertFalse(receipt["likeness_manually_reviewed"])
            self.assertTrue((installed/"ACTION_PIXEL_AUDIT.json").is_file())
            self.assertTrue((installed/"ART_REVIEW.png").exists() or
                            any("REVIEW" in p.name.upper() for p in installed.iterdir()))
            again = install_gmcy_diona(
                SOURCE_KEY, root, confirmed=True, archive_bytes=archive)
            self.assertNotEqual(installed, again)
            self.assertTrue(installed.is_dir())

    def test_reject_wrong_identity_corruption_and_missing_frame(self):
        manifest, archive = synthetic_archive()
        frames = verify_original_frames(archive, manifest=manifest)
        self.assertEqual(len(frames), 170)
        bad = copy.deepcopy(manifest)
        bad["files"][2]["git_blob_sha1"] = "a" * 40
        with self.assertRaisesRegex(ValueError, "Git blob identity mismatch"):
            verify_original_frames(archive, manifest=bad)
        with self.assertRaisesRegex(ValueError, "Wrong original"):
            install_gmcy_diona("not-diona", "/invalid", confirmed=True,
                               archive_bytes=archive)
        with io.BytesIO(archive) as src:
            with zipfile.ZipFile(src) as original:
                names = original.namelist()
                remove = next(x for x in names if x.endswith("/shime88.png"))
                zip_out = io.BytesIO()
                with zipfile.ZipFile(zip_out,"w",zipfile.ZIP_DEFLATED) as target:
                    for name in names:
                        if name != remove:
                            target.writestr(name, original.read(name))
        with self.assertRaisesRegex(ValueError, "lacks 170 original"):
            verify_original_frames(zip_out.getvalue(), manifest=manifest)


if __name__ == "__main__":
    unittest.main()

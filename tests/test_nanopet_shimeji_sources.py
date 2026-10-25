"""Pinned third-party Shimeji source audit, non-destructive offline installation."""
from __future__ import annotations

from io import BytesIO
import json
import hashlib
from pathlib import Path
import tempfile
import unittest

from PIL import Image

from tools.character_source_coverage import source_coverage
from tools.install_nanopet_shimeji import (source_manifest, install_nanopet_shimeji,
                                           GROUPS)
from tools.install_native_role import validate_native_role


class NanoPetArtistTests(unittest.TestCase):
    def test_archived_genshin_character_sources_are_real_frames(self):
        r = source_manifest()
        self.assertEqual(len(r["roles"]), 17)
        total = sum(len(x["files"]) for x in r["roles"].values())
        self.assertEqual(total, 781)
        self.assertEqual(len(r["revision"]), 40)
        self.assertNotIn("xiao-catboy-by-uuteki", r["roles"])
        expected = {
            "aether-by-tenkotenmeo": "genshin_traveler_aether",
            "lumine-by-marcia": "genshin_traveler_lumine",
            "childe-by-nemururin": "genshin_tartaglia",
            "diluc-by-vol-tuna": "genshin_diluc",
            "kaeya-by-vol-tuna": "genshin_kaeya",
            "razor-by-batsouppe": "genshin_razor",
            "xiao-by-tachi-png": "genshin_xiao",
            "zhongli-by-vol-tuna": "genshin_zhongli",
        }
        for k, profile in expected.items():
            self.assertEqual(r["roles"][k]["profile"], profile)
        for key, item in r["roles"].items():
            with self.subTest(key=key):
                self.assertGreaterEqual(len(item["files"]), 45)
                self.assertTrue(all(len(f["sha"]) == 40 for f in item["files"].values()))

    def test_123_role_ledger_does_not_exaggerate_completed_characters(self):
        r = source_coverage()
        s = r["summary"]
        self.assertEqual(s["template_count"], 123)
        self.assertEqual(s["pinned_source_options"], 53)
        self.assertEqual(s["characters_with_pinned_sources"], 30)
        self.assertEqual(s["characters_without_pinned_sources"], 93)
        self.assertEqual(s["verified_likeness_count"], 0)
        candidates = {v["id"]: v for v in r["characters"]}
        for k in ("genshin_traveler_aether", "genshin_traveler_lumine",
                  "genshin_tartaglia", "genshin_zhongli", "genshin_diluc",
                  "genshin_kaeya", "genshin_razor", "genshin_xiao"):
            self.assertTrue(candidates[k]["source_found"], k)
            self.assertTrue(any(x["provider"] == "nano_shimeji"
                                for x in candidates[k]["source_candidates"]))
        for value in r["characters"]:
            self.assertFalse(value["installed"])
            self.assertFalse(value["visual_likeness_qa_passed"])

    @staticmethod
    def image_bytes():
        data = BytesIO()
        Image.new("RGBA", (45, 72), (80, 150, 230, 200)).save(data, "PNG")
        return data.getvalue()

    def test_offline_installer_preserves_source_bytes_and_rejects_overwrite(self):
        source = self.image_bytes()
        identity = hashlib.sha1(b"blob " + str(len(source)).encode() + b"\0" + source).hexdigest()
        used = {num for values in GROUPS.values() for num in values}
        specs = {f"shime{n}.png": {"sha": identity, "size": len(source)}
                 for n in sorted(used)}
        dummy = {"repository": "Poseima/nano-pet", "revision": "a" * 40,
                 "asset_root": "NanoPetAssets/genshin-impact",
                 "roles": {"zhongli-by-vol-tuna": {
                     "name": "钟离", "profile": "genshin_zhongli",
                     "upstream_dir": "genshin-impact-zhongli-by-vol-tuna",
                     "artist": "vol-tuna", "files": specs}}}
        calls = []
        def fake_download(url, spec):
            calls.append(url)
            self.assertTrue(url.endswith(".png"))
            self.assertEqual(spec["sha"], identity)
            return source
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            with self.assertRaises(ValueError):
                install_nanopet_shimeji("zhongli-by-vol-tuna", path,
                    manifest=dummy, downloader=fake_download)
            self.assertFalse(calls)
            result = install_nanopet_shimeji("zhongli-by-vol-tuna", path,
                confirmed=True, manifest=dummy, downloader=fake_download)
            role = path / result["folder"]
            self.assertEqual((role/"action"/"stand_0.png").read_bytes(), source)
            self.assertEqual((role/"source_frames"/"shime38.png").read_bytes(), source)
            self.assertTrue((role/"ANIMATION_PREVIEW.png").is_file())
            self.assertEqual(result["source_original_frames"], len(used))
            self.assertGreaterEqual(validate_native_role(role)["actions"], 8)
            meta = json.loads((role/"PERSONAL_IMPORT.json").read_text("utf-8"))
            self.assertFalse(meta["source_rights_verified"])
            self.assertFalse(meta["likeness_manually_reviewed"])
            self.assertEqual(meta["all_original_frames_preserved"], len(used))
            with self.assertRaises(FileExistsError):
                install_nanopet_shimeji("zhongli-by-vol-tuna", path,
                    confirmed=True, manifest=dummy, downloader=fake_download)
            self.assertTrue(role.is_dir())


if __name__ == "__main__":
    unittest.main()

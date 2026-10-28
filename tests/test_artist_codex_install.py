"""Pinned public Codex art must be bound to exact immutable files."""
import hashlib
import json
import tempfile
from pathlib import Path
from unittest.mock import patch
from PIL import Image
import io
import unittest

from tools.install_artist_codex import SOURCES, REVISION, _download_pinned, install_artist_codex


class PinnedSourceTests(unittest.TestCase):
    def test_git_object_sha1_and_size(self):
        data = b"public artist source bytes"
        sha = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
        def fake_open(req, timeout=30):
            self.assertIn("raw.githubusercontent.com", req.full_url)
            return io.BytesIO(data)
        self.assertEqual(_download_pinned("https://raw.githubusercontent.com/test",
                                          (len(data), sha), opener=fake_open), data)
        with self.assertRaises(ValueError):
            _download_pinned("https://raw.githubusercontent.com/test",
                             (len(data), "0"*40), opener=fake_open)
        with self.assertRaises(ValueError):
            _download_pinned("https://raw.githubusercontent.com/test",
                             (len(data)+1, sha), opener=fake_open)

    def test_twelve_real_artist_source_ids_are_pinned(self):
        self.assertEqual(set(SOURCES), {
            "furina", "hu_tao", "klee", "nahida", "paimon", "raiden",
            "arlecchino", "ganyu", "ayaka", "navia", "yae_miko", "yoimiya"})
        self.assertEqual(len({v[0] for v in SOURCES.values()}), 12)
        for values in SOURCES.values():
            for size, digest in values[3:]:
                self.assertGreater(size, 10)
                self.assertEqual(len(digest), 40)
        self.assertEqual(len(REVISION), 40)

    def test_original_codex_install_stores_advisory_real_frame_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "res" / "role"
            pet_id = SOURCES["klee"][0]
            def fake_downloader(url, expected):
                if url.endswith("/pet.json"):
                    return json.dumps({
                        "id": pet_id, "spritesheetPath": "spritesheet.webp"
                    }).encode()
                return b"original artist bytes replaced by synthetic test fixture"
            def fake_convert(source, output, *, folder, **kwargs):
                result = Path(output) / folder
                (result / "action").mkdir(parents=True)
                (result / "pet_conf.json").write_text(json.dumps({
                    "default": "idle", "drag": "idle", "fall": "idle",
                    "left": "left", "right": "right"}))
                (result / "act_conf.json").write_text(json.dumps({
                    "idle": {"images": "idle"},
                    "left": {"images": "left"}, "right": {"images": "right"}
                }))
                for name in ("idle", "left", "right"):
                    for i in range(2):
                        img = Image.new("RGBA", (40, 48), (0, 0, 0, 0))
                        img.putpixel((10 + i, 20), (190, 120, 30, 255))
                        img.save(result / "action" / f"{name}_{i}.png")
                return result
            with patch("tools.install_artist_codex.convert",
                       side_effect=fake_convert):
                with patch("tools.install_artist_codex.validate_native_role",
                           return_value={"actions": 3, "images": 6}):
                    installed = install_artist_codex(
                        "klee", root, confirmed=True,
                        downloader=fake_downloader)
            folder = root / installed["folder"]
            receipt = json.loads((folder / "PERSONAL_IMPORT.json").read_text(encoding="utf-8"))
            report = json.loads((folder / "ANIMATION_MOTION_QA.json").read_text(encoding="utf-8"))
            self.assertEqual(installed["motion_evidence"], "ANIMATION_MOTION_QA.json")
            self.assertEqual(receipt["motion_evidence_file"], installed["motion_evidence"])
            self.assertFalse(receipt["animation_quality_automatically_approved"])
            self.assertFalse(report["rights_or_identity_certified"])
            self.assertTrue(report["manual_visual_review_pending"])
            self.assertEqual(report["actions"]["left"]["visually_distinct_samples"], 2)

    def test_motion_audit_failure_rolls_back_only_new_codex_role(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "res" / "role"
            root.mkdir(parents=True)
            prior = root / "ExistingArt"
            prior.mkdir()
            (prior / "keep.txt").write_text("do not delete", encoding="utf-8")
            pet_id = SOURCES["klee"][0]
            def fake_downloader(url, expected):
                if url.endswith("/pet.json"):
                    return json.dumps({
                        "id": pet_id, "spritesheetPath": "spritesheet.webp"
                    }).encode()
                return b"only a synthetic test fixture"

            def fake_convert(src, dest, *, folder, **kwargs):
                output = Path(dest) / folder
                output.mkdir()
                (output / "dummy.png").write_bytes(b"only-test-data")
                return output

            with patch("tools.install_artist_codex.convert",
                       side_effect=fake_convert):
                with patch("tools.install_artist_codex.validate_native_role",
                           return_value={"actions": 1, "images": 1}):
                    with patch("tools.install_artist_codex.write_motion_evidence",
                               side_effect=ValueError("bad artist frame")):
                        with self.assertRaisesRegex(ValueError, "bad artist frame"):
                            install_artist_codex(
                                "klee", root, confirmed=True,
                                downloader=fake_downloader)
            self.assertFalse((root / "SourceCodexKlee").exists())
            self.assertEqual((prior / "keep.txt").read_text(encoding="utf-8"),
                             "do not delete")

    def test_no_user_consent_no_network(self):
        with self.assertRaises(ValueError):
            install_artist_codex("klee", "/no/write/access")
        with self.assertRaises(ValueError):
            install_artist_codex("not-registered", "/no/write/access",
                                 confirmed=True)


if __name__ == "__main__":
    unittest.main()

"""Publisher ZIP tests do not convert artist-page labels into proven identity."""
from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile
from PIL import Image
from tools.probe_shimejishop_itto import (
    probe_itto, ARCHIVE, FULL_ANIMATION_ARCHIVE, bounded_download)


def fixture():
    stream = io.BytesIO()
    with ZipFile(stream, "w") as out:
        out.writestr("Start.bat", "never execute")
        for i in range(1, 47):
            picture = io.BytesIO()
            Image.new("RGBA", (48, 64),
                      ((i * 7) % 255, (i * 13) % 255, 30, 255)).save(
                      picture, format="PNG")
            out.writestr(f"Pet/img/shime{i}.png", picture.getvalue())
    return stream.getvalue()


class IttoPublisherCandidateTests(unittest.TestCase):
    def test_original_pngs_import_without_claiming_identity_or_rights(self):
        raw = fixture()
        def fetch(url):
            self.assertEqual(url, ARCHIVE)
            return raw
        evidence = probe_itto(downloader=fetch)
        self.assertEqual(evidence["profile"], "genshin_arataki_itto")
        self.assertEqual(evidence["original_png_frames"], 46)
        self.assertGreaterEqual(evidence["native_actions"], 5)
        self.assertFalse(evidence["archive_character_identity_verified"])
        self.assertFalse(evidence["character_likeness_manually_verified"])
        self.assertFalse(evidence["source_registry_promoted"])
        self.assertFalse(evidence["rights_verified"])

    def test_full_animation_link_is_bounded_and_distinct(self):
        raw = fixture()
        seen = []
        def get(url):
            seen.append(url)
            return raw
        result = probe_itto(downloader=get, archive_url=FULL_ANIMATION_ARCHIVE)
        self.assertEqual(seen, [FULL_ANIMATION_ARCHIVE])
        self.assertEqual(result["source_url"], FULL_ANIMATION_ARCHIVE)
        self.assertFalse(result["archive_character_identity_verified"])
        with self.assertRaisesRegex(ValueError, "Unknown original"):
            probe_itto(downloader=get, archive_url="https://evil.invalid/actor.zip")
        with self.assertRaisesRegex(ValueError, "Unexpected source archive"):
            bounded_download("https://evil.invalid/actor.zip")

    def test_unsupported_or_truncated_archive_refused(self):
        with self.assertRaises((ValueError, Exception)):
            probe_itto(downloader=lambda url: b"not a valid ZIP")
        with self.assertRaisesRegex(ValueError, "excessive|Invalid"):
            probe_itto(downloader=lambda url: b"x" * (32 * 1024 * 1024 + 1))


if __name__ == "__main__":
    unittest.main()

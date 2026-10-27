"""Pure offline R18 tests. Artificial PNGs test guards; not release artwork."""
from __future__ import annotations

from contextlib import contextmanager
import io
import tempfile
import unittest
from urllib.error import URLError
from zipfile import ZipFile

from PIL import Image

from tools.probe_shimejishop_kaveh import (
    ARCHIVE, MAX_DOWNLOAD, bounded_download, probe_kaveh)


def fixture():
    archive = io.BytesIO()
    with ZipFile(archive, "w") as package:
        package.writestr("Shimeji.exe", b"never run")
        package.writestr("conf/actions.xml", b"<untrusted/>")
        for idx in range(1, 47):
            img = io.BytesIO()
            Image.new("RGBA", (48, 64),
                      ((idx * 19) % 255, (idx * 11) % 255, 55, 255)).save(
                      img, format="PNG")
            package.writestr(f"Pet/img/shime{idx}.png", img.getvalue())
    return archive.getvalue()


class KavehCandidateTests(unittest.TestCase):
    def test_real_native_conversion_but_no_art_identity_claims(self):
        report = probe_kaveh(downloader=lambda url: (
            fixture() if url == ARCHIVE else None))
        self.assertEqual(report["profile"], "genshin_kaveh")
        self.assertEqual(report["original_png_frames"], 46)
        self.assertTrue(report["walk_pose_evidence_passed"])
        self.assertTrue(report["existing_kaveh_fixed_source"])
        self.assertEqual(report["new_distinct_genshin_identity_count"], 0)
        for field in ("source_registry_promoted", "artist_original_identity_verified",
                      "official_genshin_likeness_verified",
                      "artist_rights_verified", "source_art_uploaded"):
            self.assertFalse(report[field])

    def test_invalid_and_excessive_downloads_rejected(self):
        with self.assertRaisesRegex(ValueError, "archive content"):
            probe_kaveh(downloader=lambda url: b"")
        with self.assertRaisesRegex(ValueError, "archive content"):
            probe_kaveh(downloader=lambda url: b"x" * (MAX_DOWNLOAD + 1))
        with self.assertRaises(ValueError):
            probe_kaveh(downloader=lambda url: b"not-a-zip")

    def test_only_exact_https_url_and_no_external_redirects(self):
        @contextmanager
        def mock_response(url):
            class Response:
                def geturl(self):
                    return url
                def read(self, count):
                    self_read_count.append(count)
                    return b"PK\x03\x04"
            yield Response()

        self_read_count = []
        def good_opener(req, timeout):
            self.assertEqual(req.full_url, ARCHIVE)
            self.assertEqual(timeout, 25)
            return mock_response(ARCHIVE)
        self.assertEqual(
            bounded_download(opener=good_opener), b"PK\x03\x04")
        self.assertEqual(self_read_count, [MAX_DOWNLOAD + 1])

        def malicious_opener(req, timeout):
            return mock_response("https://example.invalid/kaveh.zip")
        with self.assertRaisesRegex(ValueError, "redirected outside"):
            bounded_download(opener=malicious_opener)
        with self.assertRaisesRegex(ValueError, "Unexpected"):
            bounded_download("https://evil.invalid/role.zip",
                             opener=good_opener)


if __name__ == "__main__":
    unittest.main()

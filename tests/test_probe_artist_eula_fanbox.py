"""Offline original-creator probe checks: unknown content never increases coverage."""
from __future__ import annotations
from contextlib import contextmanager
from io import BytesIO
import json
import tempfile
import unittest
from urllib.request import Request
from zipfile import ZipFile

from PIL import Image

from tools.probe_artist_eula_fanbox import (
    API_URL, AUTHOR_ID, AUTHOR_POST, POST_ID, MAX_METADATA,
    _publisher_download_url, fetch_public_post, extract_public_eula_post,
    download_creator_zip, probe_eula)


def publisher_post(files=()):
    return {"body": {
        "id": POST_ID, "creatorId": AUTHOR_ID,
        "title": "Eula Shimeji (Desktop Pet)", "isRestricted": False,
        "body": {"files": list(files)},
    }}


def fake_zip():
    contents = BytesIO()
    with ZipFile(contents, "w") as z:
        z.writestr("Shimeji-ee.jar", b"do not execute")
        for num in range(1, 47):
            fp = BytesIO()
            Image.new("RGBA", (32, 48),
                      (num * 3 % 255, num * 7 % 255, 100, 255)).save(fp, "PNG")
            z.writestr(f"Character/Eula/img/shime{num}.png", fp.getvalue())
    return contents.getvalue()


class EulaOriginalSourceTests(unittest.TestCase):
    def test_only_exact_public_creator_and_character_can_be_considered(self):
        link = ("https://downloads.fanbox.cc/files/post/8264436/"
                "Eula.zip?downloadToken=SECRET_DO_NOT_LOG")
        row = {"name": "Eula original", "extension": "zip", "url": link}
        self.assertEqual(extract_public_eula_post(publisher_post([row]))[0]["url"], link)
        # Actual 2026 public FANBOX endpoint wraps the post in body.post.
        wrapped = {"body": {"post": publisher_post([row])["body"]}}
        self.assertEqual(extract_public_eula_post(wrapped)[0]["url"], link)
        wrong = publisher_post([row])
        wrong["body"]["creatorId"] = "not-the-artist"
        with self.assertRaisesRegex(ValueError, "Wrong creator"):
            extract_public_eula_post(wrong)
        wrong = publisher_post([row])
        wrong["body"]["title"] = "Noelle shimeji"
        with self.assertRaisesRegex(ValueError, "not explicitly"):
            extract_public_eula_post(wrong)
        wrong = publisher_post([row])
        wrong["body"]["isRestricted"] = True
        with self.assertRaisesRegex(ValueError, "restricted"):
            extract_public_eula_post(wrong)
        self.assertEqual(extract_public_eula_post(publisher_post([])), [])

    def test_only_publisher_hosts_can_be_downloaded_no_urls_logged(self):
        good = "https://downloads.fanbox.cc/files/post/8264436/real.zip?token=secret"
        self.assertTrue(_publisher_download_url(good))
        for bad in ("http://downloads.fanbox.cc/file.zip",
                    "https://evil.invalid/archive.zip",
                    "https://downloads.fanbox.cc.evil.invalid/archive.zip",
                    "https://user:pass@downloads.fanbox.cc/file.zip",
                    "https://downloads.fanbox.cc:1234/file.zip"):
            self.assertFalse(_publisher_download_url(bad))
            with self.assertRaises(ValueError):
                download_creator_zip(bad)

    def test_metadata_is_bounded_and_cross_domain_redirect_refused(self):
        @contextmanager
        def response(final, raw):
            class Obj:
                def geturl(self): return final
                def read(self, count):
                    self_count.append(count)
                    return raw
            yield Obj()
        self_count = []
        sample = json.dumps(publisher_post([])).encode("utf-8")
        def opener(req, timeout):
            self.assertIsInstance(req, Request)
            self.assertEqual(req.full_url, API_URL)
            self.assertEqual(timeout, 20)
            return response(API_URL, sample)
        self.assertEqual(fetch_public_post(opener=opener), publisher_post([]))
        self.assertEqual(self_count, [MAX_METADATA + 1])
        with self.assertRaisesRegex(ValueError, "redirect"):
            fetch_public_post(opener=lambda *_a, **_kw:
                              response("https://evil.invalid/post", sample))

    def test_structurally_valid_eula_fixture_does_not_promote_source(self):
        link = "https://downloads.fanbox.cc/files/post/8264436/eula.zip"
        payload = fake_zip()
        result = probe_eula(
            post_loader=lambda: publisher_post([{"name": "eula.zip",
                                                  "extension": "zip", "url": link}]),
            downloader=lambda url: payload)
        self.assertTrue(result["source_integrity_verified"])
        self.assertEqual(result["original_png_frames"], 46)
        self.assertEqual(result["profile"], "genshin_eula")
        self.assertGreaterEqual(result["native_actions"], 6)
        self.assertFalse(result["source_registry_promoted"])
        self.assertFalse(result["rights_verified"])
        self.assertFalse(result["official_character_likeness_verified"])
        self.assertNotIn("secret", json.dumps(result).lower())

    def test_page_only_does_not_prove_character_installed(self):
        result = probe_eula(post_loader=lambda: publisher_post([]))
        self.assertFalse(result["source_integrity_verified"])
        self.assertEqual(result["public_publisher_zip_links"], 0)
        self.assertFalse(result["source_registry_promoted"])


if __name__ == "__main__":
    unittest.main()

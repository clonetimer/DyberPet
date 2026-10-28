"""R32: exact-source Codex JSON/WebP mirrors for Windows GitHub proxy blocks.

These synthetic bytes are test fixtures, NOT developer-created character art.
The identity contract is byte-for-byte Git blob SHA-1 + length, even on CDN.
"""
from __future__ import annotations

import hashlib
import json
import unittest
from urllib.error import URLError

from tools.install_artist_codex import _download_pinned, SOURCES, ROOT
from tools.pinned_github_png_transport import reset_transport_preference_for_tests

BASE = "https://raw.githubusercontent.com/legeling/awesome-codex-pet/"
REV = "db2f6306ce78f6559ab27155d7bfaf00bf43809d"


def spec(content):
    return len(content), hashlib.sha1(
        b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest()


class _Response:
    def __init__(self, address, raw):
        self.address = address
        self.raw = raw
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def geturl(self):
        return self.address
    def read(self, length):
        return self.raw[:length]


class CodexAssetFallbackTests(unittest.TestCase):
    def setUp(self):
        reset_transport_preference_for_tests()
    def tearDown(self):
        reset_transport_preference_for_tests()

    def test_same_commit_exact_git_blob_json_via_media(self):
        original = json.dumps({"id":"a-real-pinned-ID",
                               "spritesheetPath":"spritesheet.webp"}).encode()
        url = ROOT + "/citlali--zaytsevzy/pet.json"
        touched = []
        def opener(request, timeout=30):
            u = request.full_url
            touched.append(u)
            if u.startswith(BASE):
                raise URLError("Local proxy blocked raw.githubusercontent.com")
            if u.startswith("https://media.githubusercontent.com/media/"):
                return _Response(u, original)
            raise AssertionError("Not a trusted origin")
        self.assertEqual(_download_pinned(url, spec(original), opener=opener),
                         original)
        self.assertEqual(len(touched), 2)
        self.assertIn(REV, touched[-1])
        self.assertTrue(touched[-1].endswith("/citlali--zaytsevzy/pet.json"))

    def test_same_commit_exact_author_webp_via_jsdelivr(self):
        raw = b"RIFF" + b"\x18\x00\x00\x00WEBPVP8 " + b"original-binary-test"
        url = ROOT + "/citlali--zaytsevzy/spritesheet.webp"
        touched = []
        def opener(request, timeout=30):
            u = request.full_url
            touched.append(u)
            if "cdn.jsdelivr.net/gh/" in u:
                return _Response(u, raw)
            raise URLError("Original raw and media hosts unreachable")
        self.assertEqual(_download_pinned(url, spec(raw), opener=opener),raw)
        self.assertEqual(len(touched),3)
        self.assertIn("@" + REV, touched[-1])
        self.assertEqual(_download_pinned(url, spec(raw), opener=opener), raw)
        self.assertEqual(len(touched),4)  # preferred jsDelivr follows first success

    def test_rejects_wrong_bytes_or_untrusted_redirect_without_fallback(self):
        data=b"real immutable bytes"
        url=ROOT + "/citlali--zaytsevzy/pet.json"
        for wrong in ((len(data), "0"*40), (len(data)+1, spec(data)[1])):
            with self.assertRaisesRegex(ValueError,"differs"):
                _download_pinned(url, wrong,
                                 opener=lambda req,timeout=30: _Response(req.full_url,data))
        attempts=[]
        def redirect(req,timeout=30):
            attempts.append(req.full_url)
            return _Response("https://malicious.example.invalid/forgery.webp",data)
        with self.assertRaisesRegex(ValueError,"Untrusted"):
            _download_pinned(url,spec(data),opener=redirect)
        self.assertEqual(len(attempts),1)

    def test_actual_four_reported_failure_roles_still_use_immutable_refs(self):
        for key in ("ayaka","citlali","hu_tao","yae_miko"):
            pet, display, profile, meta, art = SOURCES[key]
            self.assertTrue(profile.startswith("genshin_"))
            self.assertTrue(len(meta[1])==len(art[1])==40)
            self.assertTrue(ROOT.startswith(BASE))
            self.assertGreater(art[0],1000)


if __name__=="__main__":
    unittest.main()

"""R31 no pixel substitution: hash-pinned GitHub CDN fallback for real artist PNG."""
from __future__ import annotations
import hashlib
import io
from urllib.error import URLError
import unittest
from PIL import Image

from tools.install_artist_shimeji import _download_png
from tools.pinned_github_png_transport import (
    pinned_github_png_urls, reset_transport_preference_for_tests,
)

URL = ("https://raw.githubusercontent.com/Poseima/nano-pet/"
       "abf4ec309fbe44dba6675d71c0cccb2dc419f38c/"
       "NanoPetAssets/genshin-impact/test/img/shime1.png")


def fixture():
    data = io.BytesIO()
    Image.new("RGBA", (24, 30), (100, 55, 20, 200)).save(data, format="PNG")
    raw = data.getvalue()
    return raw, {"size":len(raw),
                 "sha":hashlib.sha1(
                     b"blob " + str(len(raw)).encode()+b"\0"+raw).hexdigest()}


class Response:
    def __init__(self, url, data):
        self.url,self.data=url,data
    def __enter__(self): return self
    def __exit__(self, *a): return None
    def geturl(self): return self.url
    def read(self, n): return self.data[:n]


class R31FallbackIntegrityTests(unittest.TestCase):
    def setUp(self): reset_transport_preference_for_tests()
    def tearDown(self): reset_transport_preference_for_tests()

    def test_raw_blocked_media_fallback_same_exact_png_and_preference(self):
        raw,spec=fixture(); touched=[]
        def opener(req,timeout):
            url=req.full_url;touched.append(url)
            if url.startswith("https://raw.githubusercontent.com/"):
                raise URLError("local proxy blocked raw GitHub endpoint")
            if url.startswith("https://media.githubusercontent.com/"):
                return Response(url,raw)
            raise AssertionError("unexpected host")
        self.assertEqual(_download_png(URL,spec,opener=opener),raw)
        self.assertEqual(len(touched),2)
        self.assertEqual(_download_png(URL,spec,opener=opener),raw)
        self.assertEqual(len(touched),3)
        self.assertTrue(touched[-1].startswith("https://media.githubusercontent.com/"))

    def test_both_github_hosts_unreachable_jsdelivr_success_only_if_sha_matches(self):
        raw,spec=fixture(); touched=[]
        def opener(req,timeout):
            u=req.full_url;touched.append(u)
            if "jsdelivr.net" in u:
                return Response(u,raw)
            raise URLError("regional network unavailable")
        self.assertEqual(_download_png(URL,spec,opener=opener),raw)
        self.assertEqual(len(touched),3)
        self.assertTrue(touched[-1].startswith("https://cdn.jsdelivr.net/gh/"))
        bad=dict(spec,sha="0"*40)
        with self.assertRaisesRegex(ValueError,"Git-blob digest mismatch"):
            _download_png(URL,bad,opener=opener)

    def test_trusted_host_redirect_guard_and_no_fallback_on_bad_source(self):
        raw,spec=fixture()
        def redirected(req,timeout):
            return Response("https://malware.example.invalid/img.png",raw)
        with self.assertRaisesRegex(ValueError,"Untrusted"):
            _download_png(URL,spec,opener=redirected)
        calls=[]
        def bad_primary(req,timeout):
            calls.append(req.full_url)
            return Response(req.full_url, b"BAD PNG")
        with self.assertRaisesRegex(ValueError,"length differs"):
            _download_png(URL,spec,opener=bad_primary)
        self.assertEqual(len(calls),1)

    def test_no_mirror_for_unpinned_or_traversal_urls(self):
        for url in (
            "https://raw.githubusercontent.com/owner/repo/main/p.png",
            "http://raw.githubusercontent.com/owner/repo/"+("a"*40)+"/p.png",
            "https://raw.githubusercontent.com/owner/repo/"+("a"*40)+"/../escape.png",
            "https://evil.example.invalid/image.png",
        ):
            self.assertEqual(pinned_github_png_urls(url),(url,))

    def test_same_immutable_commit_and_relative_path_in_mirror_urls(self):
        urls=pinned_github_png_urls(URL)
        self.assertEqual(len(urls),3)
        self.assertIn("abf4ec309fbe44dba6675d71c0cccb2dc419f38c",urls[1])
        self.assertIn("@abf4ec309fbe44dba6675d71c0cccb2dc419f38c",urls[2])
        self.assertTrue(urls[1].endswith("/NanoPetAssets/genshin-impact/test/img/shime1.png"))


if __name__ == "__main__":
    unittest.main()

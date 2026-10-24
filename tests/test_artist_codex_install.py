"""Pinned public Codex art must be bound to exact immutable files."""
import hashlib
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

    def test_no_user_consent_no_network(self):
        with self.assertRaises(ValueError):
            install_artist_codex("klee", "/no/write/access")
        with self.assertRaises(ValueError):
            install_artist_codex("not-registered", "/no/write/access",
                                 confirmed=True)


if __name__ == "__main__":
    unittest.main()

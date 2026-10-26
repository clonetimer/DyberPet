"""Actual LFS art must pass exact bytes, not GitHub's pointer placeholder."""
from __future__ import annotations

import hashlib
import unittest
from unittest.mock import patch

from tools.probe_missing_react_lfs import (
    MISSING_PROFILES, candidate_urls, fetch_matching_source,
    _bounded_fetch,
)
from tools.react_shimeji_source_leads import CANDIDATES


class OriginalLfsProbeTests(unittest.TestCase):
    def test_missing_roles_only_and_immutable_upstream_hosts(self):
        self.assertEqual(MISSING_PROFILES, ("genshin_amber", "genshin_fischl"))
        for profile in MISSING_PROFILES:
            urls = candidate_urls(profile)
            self.assertEqual(len(urls), 2)
            self.assertTrue(urls[0].startswith(
                "https://media.githubusercontent.com/media/CarbonNeuron/react-shimeji/"))
            self.assertTrue(urls[1].startswith(
                "https://raw.githubusercontent.com/CarbonNeuron/react-shimeji/"))
            self.assertIn(CANDIDATES[profile][0], urls[0])
        for forbidden in ("genshin_kaveh", "genshin_fake", "../outside"):
            with self.assertRaises(ValueError):
                candidate_urls(forbidden)
        with self.assertRaisesRegex(ValueError, "Untrusted"):
            _bounded_fetch("https://example.com/evil.ts")

    def test_real_content_hash_after_pointer_is_accepted(self):
        payload = b"creator artwork original git-lfs TS module" * 30
        old = CANDIDATES["genshin_amber"]
        fixture = (old[0], hashlib.sha256(payload).hexdigest(), len(payload),
                   old[3], old[4])
        attempts = []
        def downloader(url):
            attempts.append(url)
            if len(attempts) == 1:
                return (b"version https://git-lfs.github.com/spec/v1\n"
                        b"oid sha256:bad\nsize 10\n")
            return payload
        with patch.dict(CANDIDATES, {"genshin_amber": fixture}):
            raw, source = fetch_matching_source("genshin_amber", fetch=downloader)
        self.assertEqual(raw, payload)
        self.assertIn("raw.githubusercontent.com", source)
        self.assertEqual(len(attempts), 2)

    def test_wrong_image_bytes_never_count_as_verified(self):
        with self.assertRaisesRegex(ValueError, "No real matching LFS bytes"):
            fetch_matching_source(
                "genshin_fischl", fetch=lambda url: b"not-the-original-art")
        with self.assertRaisesRegex(ValueError, "No real matching LFS bytes"):
            fetch_matching_source(
                "genshin_amber", fetch=lambda url:
                b"version https://git-lfs.github.com/spec/v1\n")


if __name__ == "__main__":
    unittest.main()

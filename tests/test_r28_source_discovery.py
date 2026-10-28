"""R28 discovery: detect NEW exact-character candidates, not download or claim art."""
from __future__ import annotations
import json
import unittest
from unittest.mock import patch
from tools.discover_new_codexpetdb_pins import (
    CATALOG_URL, query_unpinned_candidates,
)

REVISION = "019f8c79-1fd9-71eb-9425-7b39ef9d28d2"


def _pet(slug, sha="a"*64):
    return {
        "slug": slug, "revision": {"id": REVISION},
        "assets": {"byteSize": {"package": 804128},
                   "sha256": {"package": sha}}
    }


def _catalog(*rows):
    return json.dumps({
        "schemaVersion": 1,
        "assetBase": "https://cdn.codexpetdb.com/",
        "pets": list(rows)
    }).encode()


class R28ExactCatalogDiscovery(unittest.TestCase):
    def test_exact_character_id_only_and_ignore_already_covered(self):
        profiles = {
            "genshin_mona": {"name": "莫娜"},
            "genshin_bennett": {"name": "班尼特"},
            "genshin_nilou": {"name": "妮露"},
            "genshin_cyno": {"name": "赛诺"},
        }
        current = {"characters": [
            {"id": "genshin_mona", "source_found": False},
            {"id": "genshin_bennett", "source_found": False},
            {"id": "genshin_nilou", "source_found": False},
            {"id": "genshin_cyno", "source_found": True},
        ]}
        data = _catalog(_pet("gi-mona"), _pet("gi-bennet"),
                        _pet("gi-nilou"), _pet("gi-cyno"),
                        _pet("gi-nilou-alt"))
        with patch("tools.discover_new_codexpetdb_pins.CHIBI_PROFILES", profiles), \
             patch("tools.discover_new_codexpetdb_pins.source_coverage",
                   return_value=current):
            out = query_unpinned_candidates(download=lambda url: data)
        self.assertEqual(out["count"], 2)
        self.assertEqual({x["profile"] for x in out["candidates"]},
                         {"genshin_mona", "genshin_nilou"})
        self.assertTrue(all(x["catalog_only_not_download_verified"]
                            for x in out["candidates"]))
        self.assertTrue(all(x["revision"] == REVISION
                            for x in out["candidates"]))

    def test_rejects_duplicate_original_package_identity(self):
        with self.assertRaisesRegex(ValueError, "Duplicate public package identity"):
            query_unpinned_candidates(download=lambda _: _catalog(
                _pet("gi-mona"), _pet("gi-mona")))

    def test_rejects_catalog_redirection_identity_and_malformed_attestation(self):
        with self.assertRaisesRegex(ValueError, "Unexpected public catalog"):
            query_unpinned_candidates(download=lambda _: b'{"pets":[]}')
        profiles = {"genshin_mona": {"name": "莫娜"}}
        current = {"characters": [{"id": "genshin_mona", "source_found": False}]}
        with patch("tools.discover_new_codexpetdb_pins.CHIBI_PROFILES", profiles), \
             patch("tools.discover_new_codexpetdb_pins.source_coverage",
                   return_value=current):
            result = query_unpinned_candidates(download=lambda _: _catalog(
                _pet("gi-mona", sha="not-a-real-hash")))
        self.assertEqual(result["count"], 0)

    def test_current_repository_counts_are_truthful_before_new_verification(self):
        from tools.character_source_coverage import source_coverage
        summary = source_coverage()["summary"]
        self.assertEqual(summary["template_count"], 123)
        self.assertEqual(summary["characters_with_pinned_sources"], 69)
        self.assertEqual(summary["characters_without_pinned_sources"], 54)


if __name__ == "__main__":
    unittest.main()

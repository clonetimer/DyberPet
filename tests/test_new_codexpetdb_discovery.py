"""Exact new Genshin character source discovery, without metadata-only promotion."""
import json
import unittest
from unittest.mock import patch
from tools.discover_new_codexpetdb_pins import query_unpinned_candidates, CATALOG_URL


def pet(slug, sha="a" * 64):
    return {"slug": slug,
            "revision": {"id": "019f8c79-1fd9-71eb-9425-7b39ef9d28d2"},
            "assets": {"byteSize": {"package": 64000},
                       "sha256": {"package": sha}}}


class NewPublicArtDiscoveryTests(unittest.TestCase):
    def test_123_roster_expansion_and_no_false_positive(self):
        catalog = {"schemaVersion": 1, "assetBase": "https://cdn.codexpetdb.com/",
                   "pets": [pet("gi-yanfei"), pet("gi-manekina"), pet("gi-xiao"),
                            pet("gi-yelan", sha="invalid")]}
        def fetch(url):
            self.assertEqual(url, CATALOG_URL)
            return json.dumps(catalog).encode("utf-8")
        with patch("tools.discover_new_codexpetdb_pins.source_coverage",
                   return_value={"characters": [
                       {"id": "genshin_xiao", "source_found": True},
                       {"id": "genshin_yanfei", "source_found": False}]}):
            result = query_unpinned_candidates(download=fetch)
        self.assertEqual([item["profile"] for item in result["candidates"]],
                         ["genshin_yanfei"])
        self.assertTrue(result["candidates"][0]["catalog_only_not_download_verified"])

    def test_reject_duplicate_names_and_spoofed_origin(self):
        source = {"schemaVersion": 1, "assetBase": "https://cdn.codexpetdb.com/",
                  "pets": [pet("gi-yanfei"), pet("gi-yanfei")]}
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            query_unpinned_candidates(download=lambda url: json.dumps(source).encode())
        source["assetBase"] = "https://evil.invalid/"
        with self.assertRaisesRegex(ValueError, "identity"):
            query_unpinned_candidates(download=lambda url: json.dumps(source).encode())


if __name__ == "__main__":
    unittest.main()

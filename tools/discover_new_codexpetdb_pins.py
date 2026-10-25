#!/usr/bin/env python3
"""Read-only public catalog discovery for missing Genshin originals.

This script does NOT install or count art. It emits upstream package revision,
byte length and SHA as *candidate metadata* for subsequent independent ZIP
verification. It never uses fuzzy character-name matching.
"""
from __future__ import annotations

import argparse
import json
import re
from urllib.request import urlopen, Request

try:
    from .community_codex_leads import PROFILE_TO_SLUG
    from .character_source_coverage import source_coverage
except ImportError:
    from community_codex_leads import PROFILE_TO_SLUG
    from character_source_coverage import source_coverage

CATALOG_URL = "https://cdn.codexpetdb.com/catalogs/v1/pets.json"
MAX_CATALOG_BYTES = 10 * 1024 * 1024
REVISION = re.compile(r"^[0-9a-f]{8}-(?:[0-9a-f]{4}-){2}7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")
SHA = re.compile(r"^[0-9a-f]{64}$")


def query_unpinned_candidates(*, download=None):
    if download is None:
        def download(url):
            req = Request(url, headers={"User-Agent": "DyberPet-source-review/1"})
            with urlopen(req, timeout=20) as response:
                if response.geturl() != CATALOG_URL:
                    raise ValueError("Public catalog redirected to untrusted origin")
                return response.read(MAX_CATALOG_BYTES + 1)
    raw = download(CATALOG_URL)
    if not isinstance(raw, bytes) or len(raw) > MAX_CATALOG_BYTES:
        raise ValueError("Source catalog exceeds bounded size")
    catalog = json.loads(raw)
    if (catalog.get("schemaVersion") != 1 or
            catalog.get("assetBase") != "https://cdn.codexpetdb.com/" or
            not isinstance(catalog.get("pets"), list)):
        raise ValueError("Unexpected public catalog identity or structure")
    registered = {x["id"] for x in source_coverage()["characters"]
                  if x["source_found"]}
    by_slug = {}
    for entry in catalog["pets"]:
        if not isinstance(entry, dict) or not isinstance(entry.get("slug"), str):
            continue
        if entry["slug"] in by_slug:
            raise ValueError("Duplicate public package identity")
        by_slug[entry["slug"]] = entry
    findings = []
    for profile, slug in sorted(PROFILE_TO_SLUG.items()):
        if profile in registered or slug not in by_slug:
            continue
        pet = by_slug[slug]
        version = pet.get("revision") or {}
        assets = pet.get("assets") or {}
        sizes = assets.get("byteSize") or {}
        hashes = assets.get("sha256") or {}
        rid = version.get("id")
        size = sizes.get("package")
        sha = hashes.get("package")
        if (not isinstance(rid, str) or REVISION.fullmatch(rid) is None or
                type(size) is not int or not 0 < size <= 3 * 1024 * 1024 or
                not isinstance(sha, str) or SHA.fullmatch(sha) is None):
            continue
        findings.append({
            "profile": profile, "slug": slug, "revision": rid,
            "sha256": sha, "verified_bytes": size,
            "max_bytes": 3_000_000,
            "listing_url": "https://codexpetdb.com/en/pets/" + slug + "/download",
            "catalog_only_not_download_verified": True,
        })
    return {
        "scope": "discovery_only_not_integrity_verified",
        "count": len(findings),
        "candidates": findings,
        "warning": "Never add to source coverage until matching ZIP bytes, pet.json ID and original atlas pass an independent test; visual identity is a separate review.",
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=25)
    args = ap.parse_args(argv)
    report = query_unpinned_candidates()
    report["candidates"] = report["candidates"][:max(0, min(args.limit, 60))]
    print(json.dumps(report, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

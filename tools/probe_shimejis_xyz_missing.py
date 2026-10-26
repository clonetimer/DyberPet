#!/usr/bin/env python3
"""Exact Genshin Shimejis directory leads: not installed or visually approved.

Use only the upstream Genshin collection page. Parse no script or executable;
never access entire shimejis.xyz collection. Metadata-only candidates are
excluded from the fixed artist source register until genuine native frames,
source identity, action integrity and rights receive independent review.
"""
from __future__ import annotations

import argparse
from html.parser import HTMLParser
import json
import re
import sys
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

if __package__ in (None, ""):
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.character_source_coverage import source_coverage

PACK_URL = "https://shimejis.xyz/directory/genshin-impact-shimeji-pack"
MAX_BYTES = 750_000
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class _CharacterLinks(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.slugs = set()

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "a":
            return
        href = dict(attrs).get("href", "")
        if not isinstance(href, str):
            return
        parsed = urlsplit(href)
        if parsed.scheme not in ("", "https") or (
                parsed.hostname is not None and parsed.hostname not in
                ("shimejis.xyz", "www.shimejis.xyz")):
            return
        path = parsed.path.rstrip("/")
        prefix = "/directory/shimeji/"
        if path.startswith(prefix):
            token = path[len(prefix):]
            if SLUG.fullmatch(token):
                self.slugs.add(token)


def _fetch_page():
    req = Request(PACK_URL, headers={
        "User-Agent": "DyberPet-artist-source-identity-research/1"})
    with urlopen(req, timeout=20) as result:
        final = urlsplit(result.geturl())
        if final.scheme != "https" or final.hostname not in (
                "shimejis.xyz", "www.shimejis.xyz"):
            raise ValueError("Unexpected Shimeji source redirect")
        body = result.read(MAX_BYTES + 1)
    if len(body) > MAX_BYTES:
        raise ValueError("Upstream Genshin collection HTML exceeds the read limit")
    return body.decode("utf-8")


def _key_in_slug(key, slug):
    # Delimited exact roster IDs, never substring-only matches. Multiple hits
    # are considered ambiguous and suppressed rather than guessed.
    token = key.removeprefix("genshin_").replace("_", "-")
    return re.search(r"(?:^|-)" + re.escape(token) + r"(?:-|$)", slug) is not None


def candidate_report(*, page=None, coverage=None):
    page = _fetch_page() if page is None else page
    if not isinstance(page, str) or len(page.encode("utf-8")) > MAX_BYTES:
        raise ValueError("Invalid bounded HTML document")
    index = _CharacterLinks()
    index.feed(page)
    if not index.slugs:
        raise ValueError("Genshin source page exposed no public character links")
    summary = source_coverage() if coverage is None else coverage
    rows = summary["characters"]
    missing = {row["id"]: row for row in rows if not row["source_found"]}
    all_ids = [row["id"] for row in rows]
    candidates, ambiguous, already = [], [], []
    for slug in sorted(index.slugs):
        matches = [key for key in all_ids if _key_in_slug(key, slug)]
        if len(matches) != 1:
            ambiguous.append({"slug": slug, "matches": matches})
            continue
        profile = matches[0]
        if profile not in missing:
            already.append({"profile": profile, "slug": slug})
            continue
        candidates.append({
            "profile": profile,
            "name": missing[profile]["name"],
            "slug": slug,
            "page": "https://shimejis.xyz/directory/shimeji/" + slug,
            "publisher_metadata_only": True,
            "original_png_verified": False,
            "original_character_identity_verified": False,
            "original_visual_likeness_approved": False,
            "action_structure_verified": False,
            "source_rights_verified": False,
            "pinned_source_promoted": False,
        })
    return {
        "scope": "untrusted_public_candidate_directory_only",
        "source_page": PACK_URL,
        "linked_slugs": len(index.slugs),
        "uncovered_matching_candidates": len(candidates),
        "previously_covered_matches": len(already),
        "unmatched_or_ambiguous": len(ambiguous),
        "candidates": candidates,
        "ambiguous": ambiguous[:25],
        "coverage_registry_unchanged": True,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--max-print", type=int, default=40)
    a = p.parse_args()
    report = candidate_report()
    print("GENSHIN_SHIMEJIS_XYZ_CANDIDATES " +
          json.dumps(report, ensure_ascii=False, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

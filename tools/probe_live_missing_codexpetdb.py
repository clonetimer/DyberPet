#!/usr/bin/env python3
"""CI-only full-ZIP verification for newly published exact-roster Genshin art.

No external code is executed, images are not uploaded, and even successful
checks cannot assert artist likeness, usage rights or actual physical playback.
"""
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

try:
    from .discover_new_codexpetdb_pins import query_unpinned_candidates
    from .install_pinned_codexpetdb import (
        get_verified_package, inspect_codex_zip, install_pinned_codexpetdb)
    from .install_native_role import validate_native_role
except ImportError:
    from discover_new_codexpetdb_pins import query_unpinned_candidates
    from install_pinned_codexpetdb import (
        get_verified_package, inspect_codex_zip, install_pinned_codexpetdb)
    from install_native_role import validate_native_role


def probe(limit=6):
    if not 1 <= limit <= 12:
        raise ValueError("Use 1-12 source candidates")
    leads = query_unpinned_candidates()["candidates"]
    leads.sort(key=lambda x: (x["profile"] != "genshin_yanfei", x["profile"]))
    results, failures = [], []
    with tempfile.TemporaryDirectory(prefix="dyberpet-new-art-source-") as td:
        root = Path(td)
        for item in leads[:limit]:
            profile = item["profile"]
            key = profile[len("genshin_"):]
            meta = {k: v for k, v in item.items()
                    if k != "catalog_only_not_download_verified"}
            manifest = {"schema": 1, "provider": "CodexPetDB",
                        "sources": {key: meta}}
            try:
                raw, source = get_verified_package(key, manifest=manifest)
                archive = root / (source["slug"] + ".zip")
                archive.write_bytes(raw)
                original = inspect_codex_zip(archive)
                if original["manifest"]["id"] != source["slug"]:
                    raise ValueError("Archive contains a mismatched character ID")
                role = install_pinned_codexpetdb(
                    key, root / "installed", confirmed=True,
                    archive=archive, manifest=manifest)
                native = validate_native_role(role)
                audit = json.loads((role / "ACTION_PIXEL_AUDIT.json").read_text("utf-8"))
                receipt = json.loads((role / "PERSONAL_IMPORT.json").read_text("utf-8"))
                if (receipt["selected_profile"] != profile or
                        receipt["source_zip_sha256_verified"] != source["sha256"] or
                        native["images"] < 30 or native["actions"] < 5 or
                        not audit["summary"]["animation_structure_passed"] or
                        not (role / "ANIMATION_PREVIEW.png").is_file()):
                    raise ValueError("Native image/action structural gate did not pass")
                evidence = {
                    "profile": profile, "revision": source["revision"],
                    "slug": source["slug"], "sha256": source["sha256"],
                    "verified_bytes": len(raw), "max_bytes": source["max_bytes"],
                    "listing_url": source["listing_url"],
                    "native_actions": native["actions"],
                    "source_frames": audit["summary"]["original_frames_inspected"],
                    "human_visual_likeness_approved": False,
                    "actual_desktop_playback_approved": False,
                    "rights_verified": False}
                results.append(evidence)
                print("NEW_PUBLIC_SOURCE_FULLY_VERIFIED " +
                      json.dumps(evidence, sort_keys=True), flush=True)
            except (OSError, ValueError, TypeError, KeyError) as err:
                failure = {"profile": profile, "error": str(err)[:180]}
                failures.append(failure)
                print("NEW_PUBLIC_SOURCE_UNVERIFIED " +
                      json.dumps(failure, sort_keys=True), flush=True)
    print("NEW_SOURCE_DISCOVERY_SUMMARY " + json.dumps({
        "candidates": len(leads), "checked": min(limit, len(leads)),
        "passed": len(results), "unverified": len(failures),
        "promoted": 0, "human_visual_likeness_approved": 0}, sort_keys=True))
    return results, len(leads)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=6)
    args = parser.parse_args(argv)
    passed, candidates = probe(args.limit)
    # When all known public archives have been verified and pinned,
    # zero *new* candidates is a normal success, not a red CI signal.
    return 0 if not candidates or passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""CI-only: verify new public Genshin ZIPs before promoting them to source registry.

Never runs any downloaded executable. Downloads one archive per role, verifies
full SHA and observed byte size, validates source identity, then checks that
the existing native converter accepts real atlas pixels and produces a usable
role plus original-frame audit. No artwork is uploaded or redistributed.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import tempfile
import time

try:
    from .install_pinned_codexpetdb import (
        get_verified_package, inspect_codex_zip, install_pinned_codexpetdb)
    from .install_native_role import validate_native_role
except ImportError:
    from install_pinned_codexpetdb import (
        get_verified_package, inspect_codex_zip, install_pinned_codexpetdb)
    from install_native_role import validate_native_role

PENDING = Path(__file__).with_name("codexpetdb_pending_zip_leads.json")


def verify_new_sources(candidate_file=PENDING):
    entries = json.loads(Path(candidate_file).read_text(encoding="utf-8"))
    if (entries.get("status") != "catalog_metadata_only_not_verified" or
            entries.get("schema") != 1 or
            len(entries.get("sources", {})) != 4):
        raise ValueError("Untrusted candidate source registry")
    results = []
    with tempfile.TemporaryDirectory(prefix="new-role-source-qa-") as temp:
        root = Path(temp)
        for index, (key, metadata) in enumerate(sorted(entries["sources"].items())):
            if index:
                time.sleep(1.5)  # Don't flood the community CDN.
            payload, source = get_verified_package(key, manifest=entries)
            local = root / (source["slug"] + ".zip")
            local.write_bytes(payload)
            inspected = inspect_codex_zip(local)
            if inspected["manifest"]["id"] != source["slug"]:
                raise ValueError("Source ZIP contains a different character")
            installed = install_pinned_codexpetdb(
                key, root / "installed", archive=local, manifest=entries,
                confirmed=True)
            validation = validate_native_role(installed)
            audit = json.loads((installed / "ACTION_PIXEL_AUDIT.json").read_text("utf-8"))
            receipt = json.loads((installed / "PERSONAL_IMPORT.json").read_text("utf-8"))
            if (validation["images"] < 30 or validation["actions"] < 5 or
                    receipt["selected_profile"] != metadata["profile"] or
                    audit["summary"]["actions_with_pixel_issues"] or
                    not (installed / "ANIMATION_PREVIEW.png").is_file()):
                raise ValueError("Original art failed native role or pixel quality gate")
            results.append({
                "profile": metadata["profile"], "key": key,
                "revision": source["revision"], "sha256": source["sha256"],
                "bytes": len(payload),
                "native_actions": validation["actions"],
                "source_frames": audit["summary"]["original_frames_inspected"],
                "character_likeness_manually_verified": False,
                "independent_actual_bytes_verified": True,
                "native_install_verified": True,
            })
            print("NEW_SOURCE_VERIFIED", json.dumps(results[-1], sort_keys=True))
    if len(results) != 4:
        raise ValueError("Not every proposed source was verified")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-file", type=Path, default=PENDING)
    args = parser.parse_args()
    verify_new_sources(args.candidate_file)

#!/usr/bin/env python3
"""Honest 123-character source coverage: references are NOT installed or QA approved."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.parse import quote

try:
    from .chibi_profiles import CHIBI_PROFILES
    from .creator_art_preference import source_style, candidate_character_style
    from .install_artist_codex import SOURCES as CODEX, REVISION as CODEX_REV, REPO as CODEX_REPO
    from .install_artist_genshin import ROLES as NATIVE, REVISION as NATIVE_REV, REPOSITORY as NATIVE_REPO
    from .install_artist_shimeji import source_manifest
    from .install_nanopet_shimeji import source_manifest as nano_manifest
    from .install_external_codex import source_manifest as external_manifest
except ImportError:
    from chibi_profiles import CHIBI_PROFILES
    from creator_art_preference import source_style, candidate_character_style
    from install_artist_codex import SOURCES as CODEX, REVISION as CODEX_REV, REPO as CODEX_REPO
    from install_artist_genshin import ROLES as NATIVE, REVISION as NATIVE_REV, REPOSITORY as NATIVE_REPO
    from install_artist_shimeji import source_manifest
    from install_nanopet_shimeji import source_manifest as nano_manifest
    from install_external_codex import source_manifest as external_manifest


def source_coverage():
    names = {k: v["name"] for k, v in CHIBI_PROFILES.items()
             if k.startswith("genshin_")}
    rows = {k: {"id": k, "name": label, "source_candidates": [],
                "source_found": False, "installed": False,
                "visual_likeness_qa_passed": False, "rights_verified": False,
                "windows_desktop_qa_passed": False,
                "visual_grade": None}
            for k, label in sorted(names.items())}

    def record(profile, provider, key, url):
        if profile not in rows:
            raise ValueError("Pinned creator asset maps to unknown character: " + profile)
        rows[profile]["source_candidates"].append({
            "provider": provider, "source_key": key,
            "url": url, "asset_is_bundled": False,
            "needs_manual_likeness_and_rights_review": True,
            **source_style(provider),
        })
        rows[profile]["source_found"] = True

    for kind, (pet_id, _label, profile, *_hashes) in CODEX.items():
        record(profile, "codex", kind,
               f"https://github.com/{CODEX_REPO}/tree/{CODEX_REV}/pets/{pet_id}")
    for kind, (folder, profile, _label) in NATIVE.items():
        record(profile, "native", kind,
               f"https://github.com/{NATIVE_REPO}/tree/{NATIVE_REV}/res/role/{quote(folder)}")
    src = source_manifest()
    for kind, asset in src["roles"].items():
        record(asset["profile"], "shimeji", kind,
               f"https://github.com/{src['repository']}/tree/{src['revision']}/public/assets/{kind}")
    nano = nano_manifest()
    for kind, asset in nano["roles"].items():
        record(asset["profile"], "nano_shimeji", kind,
               f"https://github.com/{nano['repository']}/tree/{nano['revision']}/{nano['asset_root']}/{asset['upstream_dir']}/img")
    external = external_manifest()
    for kind, asset in external["sources"].items():
        record(asset["profile"], "independent_codex", kind,
               f"https://github.com/{asset['repository']}/tree/{asset['revision']}/{asset['directory']}")
    # These approved r1 packages were independently downloaded and SHA-256
    # verified against source bytes in the CI provider-zip-integrity job.
    # This is *source integrity* coverage, never human character likeness.
    petdb = json.loads(Path(__file__).with_name(
        "codexpetdb_pinned_zip_leads.json").read_text(encoding="utf-8"))
    if petdb.get("schema") != 1 or not 24 <= len(petdb.get("sources", {})) <= 123:
        raise ValueError("Invalid SHA-256-verified community art source registry")
    for key, asset in sorted(petdb["sources"].items()):
        if asset["profile"] not in rows or len(asset["sha256"]) != 64:
            raise ValueError("New community art source references unknown character")
        url = ("https://cdn.codexpetdb.com/revisions/" +
               asset["revision"] + "/" + asset["slug"] + ".zip")
        record(asset["profile"], "codexpetdb_zip", key, url)
        rows[asset["profile"]]["source_candidates"][-1].update({
            "archive_sha256": asset["sha256"],
            "byte_integrity_tested_in_ci": True,
            "contains_original_atlas_verified": True,
            "artist_character_likeness_verified": False,
            "native_role_installed_by_report": False,
        })
    for item in rows.values():
        item["source_candidates"].sort(key=lambda c: (c["preference_order"], c["provider"], c["source_key"]))
        item["recommended_source"] = item["source_candidates"][0] if item["source_candidates"] else None
        item["style_preference_text"], item["style_preference_group"] = candidate_character_style(item["source_candidates"])
        item["source_candidate_count"] = len(item["source_candidates"])
    available = [v for v in rows.values() if v["source_found"]]
    return {
        "scope": "pinned_source_discovery_only",
        "summary": {
            "template_count": len(rows),
            "pinned_source_options": sum(len(v["source_candidates"]) for v in rows.values()),
            "characters_with_pinned_sources": len(available),
            "characters_without_pinned_sources": len(rows) - len(available),
            "style_priority_detailed_native_count": sum(v["style_preference_group"] == "detailed_candidate" for v in available),
            "style_priority_atlas_pending_count": sum(v["style_preference_group"] == "atlas_review" for v in available),
            "style_priority_shimeji_candidate_count": sum(v["style_preference_group"] == "small_candidate" for v in available),
            "user_visible_style_grades_approved": 0,
            "verified_likeness_count": 0,
            "installed_by_this_report": 0,
            "rights_verified_count": 0,
            "physical_windows_qa_count": 0,
        },
        "note": ("Public accessibility or checksum pinning does not certify copyright permissions, "
                 "original-game appearance, correct animation, install success or visual acceptance. "
                 "Missing characters MUST NOT be replaced by generic simplified art. "
                 "P1/P2 style sorting is not an A/B/C likeness grade; all visual reviews remain pending."),
        "characters": list(rows.values()),
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--missing-only", action="store_true")
    p.add_argument("--output", type=Path, help="Optional UTF-8 JSON report")
    args = p.parse_args(argv)
    result = source_coverage()
    if args.missing_only:
        result["characters"] = [r for r in result["characters"] if not r["source_found"]]
    output = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output is not None:
        args.output.write_text(output, encoding="utf-8")
    else:
        # Windows CI/PowerShell may launch the script with cp1252 stdout,
        # which cannot encode Chinese role names. Produce real UTF-8 JSON.
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="strict")
        print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

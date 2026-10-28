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
    if petdb.get("schema") != 1 or not 28 <= len(petdb.get("sources", {})) <= 123:
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
    # Exact original LFS bytes and native install were independently verified
    # in CI; this is source integrity only, not full motion/likeness approval.
    react = json.loads(Path(__file__).with_name(
        "react_lfs_verified_sources.json").read_text(encoding="utf-8"))
    if react.get("schema") != 1 or len(react.get("sources", {})) != 4:
        raise ValueError("Unexpected verified React-Shimeji source registry")
    for key, entry in sorted(react["sources"].items()):
        profile = entry["profile"]
        if (profile not in rows or len(entry["sha256"]) != 64 or
                not isinstance(entry["verified_bytes"], int) or
                entry["verified_bytes"] < 100):
            raise ValueError("Invalid verified upstream React-Shimeji source")
        link = ("https://github.com/" + react["repository"] + "/tree/" +
                react["revision"] + "/packages/character-" + entry["slug"])
        record(profile, "react_lfs", key, link)
        rows[profile]["source_candidates"][-1].update({
            "full_lfs_source_sha256": entry["sha256"],
            "full_lfs_bytes_verified_in_ci": entry["verified_bytes"],
            "native_install_tested_in_ci": True,
            "real_original_png_frames_verified": entry["atlas_frames"],
            "action_quality_pending": entry["action_quality_pending"],
            "artist_character_likeness_verified": False,
            "physical_runtime_motion_qa_verified": False,
        })
    # R28: GMCY creator explicitly identifies pet_2 as Genshin Diona;
    # 170 original PNG Git blobs and nine native action groups passed isolated CI.
    gmcy = json.loads(Path(__file__).with_name("gmcy_diona_170_source.json").read_text(encoding="utf-8"))
    if (gmcy.get("schema") != 1 or gmcy.get("source_profile") != "genshin_diona"
            or gmcy.get("original_frame_count") != 170 or
            len(gmcy.get("files", [])) != 170 or
            len(gmcy.get("original_action_groups", [])) != 9):
        raise ValueError("Invalid independently verified GMCY Diona 170 source registry")
    record("genshin_diona", "gmcy_diona", "diona_170",
           "https://github.com/" + gmcy["repository"] + "/tree/" + gmcy["commit"] + "/resources/pet_2")
    rows["genshin_diona"]["source_candidates"][-1].update({
        "original_author_frames": 170,
        "verified_original_git_blob_count": 170,
        "original_creator_action_groups": 9,
        "native_source_import_tested_in_ci": True,
        "source_author_likeness_qa_passed": False,
        "action_semantics_manually_approved": False,
        "artist_rights_approved": False,
        "prebundled_original_art": False,
    })
    # R29: independent GMCY pet_1: Genshin Keqing / 刻晴; 92 real PNG frames,
    # exact per-file Git object identities, six author action sequences.
    keqing = json.loads(Path(__file__).with_name("gmcy_keqing_92_source.json").read_text(encoding="utf-8"))
    if (keqing.get("schema") != 1 or keqing.get("source_profile") != "genshin_keqing"
            or keqing.get("source_directory") != "resources/pet_1"
            or keqing.get("original_frame_count") != 92 or
            len(keqing.get("files", [])) != 92 or
            len(keqing.get("original_action_groups", [])) != 6):
        raise ValueError("Invalid source-pinned GMCY Keqing 92 registry")
    record("genshin_keqing", "gmcy_keqing", "keqing_92",
           "https://github.com/" + keqing["repository"] + "/tree/" +
           keqing["commit"] + "/resources/pet_1")
    rows["genshin_keqing"]["source_candidates"][-1].update({
        "original_author_frames": 92,
        "verified_original_git_blob_count": 92,
        "original_creator_action_groups": 6,
        "native_source_import_tested_in_ci": True,
        "source_author_likeness_qa_passed": False,
        "action_semantics_manually_approved": False,
        "artist_rights_approved": False,
        "prebundled_original_art": False,
    })
    # Original creator public ZIP and 109 numbered PNGs independently
    # SHA-verified in CI, not bundled or visually approved.
    # Keep this catalog directly runnable as python tools/character_source_coverage.py
    # on Windows where the package root may not be on sys.path. The public
    # byte constants are cross-checked against the installer by its tests.
    EULA_SOURCE = "eula_saylamars_original"
    EULA_BYTES = 8400168
    EULA_EXTENDED_SOURCE_SHA256 = (
        "f4952ea151e0ead70b501e9e2637f9dae1194e0da1b5d312046964fc19046803")
    record("genshin_eula", "pinned_eula_creator", EULA_SOURCE,
           "https://saylamars.fanbox.cc/posts/8264436")
    rows["genshin_eula"]["source_candidates"][-1].update({
        "archive_sha256": EULA_EXTENDED_SOURCE_SHA256,
        "verified_zip_bytes": EULA_BYTES,
        "verified_numbered_original_pngs": 109,
        "verified_native_actions": 15,
        "extended_author_frames_preserved_not_semantically_promoted": True,
        "creator_own_post_verified": True,
        "artist_character_likeness_verified": False,
        "rights_verified": False,
        "physical_desktop_qa_verified": False,
        "archive_is_bundled": False,
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

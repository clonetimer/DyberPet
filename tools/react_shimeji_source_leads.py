#!/usr/bin/env python3
"""Git-LFS-pinned external React-Shimeji character *leads*, not usable art.

GitHub's small index.ts blobs contain LFS pointers, NOT actual animation
bytes. Do not count them as imported or visually accepted characters.
Never execute third-party TypeScript, install npm packages, or assume that a
repository's MIT label automatically settles original game art rights.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from .character_source_coverage import source_coverage
    from .chibi_profiles import CHIBI_PROFILES
except ImportError:
    from character_source_coverage import source_coverage
    from chibi_profiles import CHIBI_PROFILES

REPOSITORY = "CarbonNeuron/react-shimeji"
REVISION = "35b507062be71e8b9dbea6d20b77a9901dfe9114"
# Stable content identities returned directly by upstream GitHub API.
# tuple: upstream package suffix, LFS SHA-256 OID, LFS declared byte count,
# Git blob SHA of the pointer, optional preview.png Git blob SHA.
CANDIDATES = {
    "genshin_alhaitham": ("alhaitham-13f681",
        "eecfcecce33b53edda699db13a4ae2f462a2d2024589b645cf1e27c7cd5799a5",
        985661, "c896c42a44a874205e12b3e5ef0756a44f031467",
        "392838304dc53f6400494bc6a1be36d4dbb54268"),
    "genshin_amber": ("amber-ef95b4",
        "5f5e95242604640a48ae340f097063cf01ea17460ec1818a9c8ba768f88c426d",
        783823, "98d7c74343d5e5f19f39c42ac241ead12fabfc5d", None),
    "genshin_columbina": ("columbina-f9104f",
        "f566e7766b541a48c09fc7991cc80dbc126b6aa587893432bc2d4ac351ad31ad",
        929977, "f3ecff828c5fee20409d7f64b4368fe5bf647d11",
        "620e98bc8252327143c95de11b1367f40b47b5c2"),
    "genshin_fischl": ("fischl-f4f4f5",
        "1e238f494fe023babc20421832b21509182d39ab0c7fa7650942acca6c5530dc",
        703235, "82b085061d8293bfd6c932be560980dfab213a06",
        "bb9458789d76188208eee469adfe1820208937b2"),
    "genshin_freminet": ("freminet-d08ecb",
        "70c45bd439c2c182be8dafa0f8febc421fbf96ca6c39d0453bbc7aac4eb1f7d1",
        1099264, "9fa72e92706c3e2af1a876b7fadc7cfd1650de77", None),
    "genshin_kaveh": ("kaveh-2f46f2",
        "5abe02c8363a86b2c849277409aed0c28d0b606fbde87747f5771f89a23ee922",
        1176253, "6377f1b50d24bf02bea629741f702c6a56337a94",
        "9ddd26c6c463690746eb50a82e6c6cfa2a93111b"),
}



def verified_lfs_sources():
    """Return only full-byte/CI-verified source records, never pointer leads."""
    catalog = json.loads(Path(__file__).with_name(
        "react_lfs_verified_sources.json").read_text(encoding="utf-8"))
    if catalog.get("schema") != 1 or len(catalog.get("sources", {})) != 2:
        raise ValueError("Unexpected original-LFS source registry")
    mapped = {}
    for key, entry in catalog["sources"].items():
        profile = entry["profile"]
        if profile not in CANDIDATES or profile in mapped:
            raise ValueError("Verified source has no exact roster identity")
        upstream = CANDIDATES[profile]
        if (upstream[0] != entry["slug"] or
                upstream[1] != entry["sha256"] or
                upstream[2] != entry["verified_bytes"] or
                catalog["revision"] != REVISION or
                catalog["repository"] != REPOSITORY):
            raise ValueError("Verified source attestation disagrees with upstream LFS pointer")
        mapped[profile] = entry
    return mapped


def react_shimeji_lead_report():
    pinned = {x["id"]: x["source_found"] for x in source_coverage()["characters"]}
    verified_profiles = set(verified_lfs_sources())
    rows = []
    for profile, (slug, oid, size, pointer_blob, preview_blob) in sorted(CANDIDATES.items()):
        if profile not in CHIBI_PROFILES or not profile in pinned:
            raise ValueError("Unknown Genshin template: " + profile)
        if (len(oid) != 64 or len(pointer_blob) != 40 or
                (preview_blob is not None and len(preview_blob) != 40) or
                not 100 < size < 10_000_000):
            raise ValueError("Invalid pinned LFS pointer metadata")
        folder = "packages/character-" + slug
        rows.append({
            "id": profile,
            "name": CHIBI_PROFILES[profile]["name"],
            "source_url": f"https://github.com/{REPOSITORY}/tree/{REVISION}/{folder}",
            "preview_url": (f"https://github.com/{REPOSITORY}/blob/{REVISION}/"
                            + folder + "/preview.png") if preview_blob else None,
            "lfs_pointer_url": f"https://github.com/{REPOSITORY}/blob/{REVISION}/{folder}/index.ts",
            "lfs_content_sha256_expected": oid,
            "lfs_content_declared_bytes": size,
            "lfs_pointer_git_blob_sha": pointer_blob,
            "preview_png_git_blob_sha": preview_blob,
            "existing_fixed_source": bool(pinned[profile]),
            "status": ("original_bytes_sha_native_install_verified_motion_pending"
                       if profile in verified_profiles else
                       "lfs_pointer_verified_art_uninspected"),
            "full_lfs_art_downloaded_and_hashed": profile in verified_profiles,
            "native_install_tested_in_ci": profile in verified_profiles,
            "motion_action_quality_pending": (["crawl", "fall"] if profile in verified_profiles else []),
            "visual_likeness_qa_passed": False,
            "native_role_installed": False,  # never installed by this read-only report
            "redistribution_rights_verified": False,
        })
    return {
        "scope": "source_leads_only_no_automatic_art_install",
        "summary": {
            "repo_character_packages": 2224,
            "matched_distinct_genshin_personas": len(rows),
            "new_leads_for_missing_characters": sum(not r["existing_fixed_source"] for r in rows),
            "fixed_source_coverage_unchanged": True,
            "source_origins_verified_in_ci": len(verified_profiles),
            "downloaded_or_installed": 0,  # local user installs not performed
            "art_qa_passed": 0,
        },
        "characters": rows,
        "warning": ("The upstream .ts path is a Git LFS pointer in GitHub's standard "
                    "contents API. The pointer's SHA256 is a verification target, NOT "
                    "proof that the full animation was retrieved or of visual identity. "
                    "The upstream MIT package label is not a game IP clearance."),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    text = json.dumps(react_shimeji_lead_report(), ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

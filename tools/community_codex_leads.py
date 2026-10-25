#!/usr/bin/env python3
"""Curated public *leads*, not verified artist art or a download registry.

CodexPetDB's Genshin Impact collection displayed 35 entries on 2026-10-25.
Two Manekina variations do not map to this roster and are excluded. These
URLs are a manual visual-review shortlist only: NEVER add to pinned counts.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from .chibi_profiles import CHIBI_PROFILES
    from .character_source_coverage import source_coverage
except ImportError:
    from chibi_profiles import CHIBI_PROFILES
    from character_source_coverage import source_coverage

CATALOG_URL = "https://codexpetdb.com/en/collections/genshin-impact"
CATALOG_DATE = "2026-10-25"
# These 33 entries have exact, unique profile mappings in our local roster.
# The separate gi-manekina / gi-manekina-2 entries are not a Genshin
# character template and must never inflate the 123 roster.
PROFILE_TO_SLUG = {
    "genshin_alyosha": "gi-alyosha",
    "genshin_odette": "gi-odette",
    "genshin_sandrone": "gi-sandrone",
    "genshin_linnea": "gi-linnea",
    "genshin_ayaka": "ayaka",
    "genshin_prune": "gi-prune",
    "genshin_aino": "gi-aino",
    "genshin_arlecchino": "gi-arlecchino",
    "genshin_alhaitham": "gi-alhaitham",
    "genshin_baizhu": "gi-baizhu",
    "genshin_candace": "gi-candace",
    "genshin_chevreuse": "gi-chevreuse",
    "genshin_charlotte": "gi-charlotte",
    "genshin_chiori": "gi-chiori",
    "genshin_columbina": "gi-columbina",
    "genshin_dahlia": "gi-dahlia",
    "genshin_cyno": "gi-cyno",
    "genshin_dehya": "gi-dehya",
    "genshin_durin": "gi-durin",
    "genshin_emilie": "gi-emilie",
    "genshin_flins": "gi-flins",
    "genshin_freminet": "gi-freminet",
    "genshin_gaming": "gi-gaming",
    "genshin_iansan": "gi-iansan",
    "genshin_ineffa": "gi-ineffa",
    "genshin_jahoda": "gi-jahoda",
    "genshin_kaveh": "gi-kaveh",
    "genshin_kinich": "gi-kinich",
    "genshin_kirara": "gi-kirara",
    "genshin_lan_yan": "gi-lan-yan",
    "genshin_lauma": "gi-lauma",
    "genshin_layla": "gi-layla",
    "genshin_lohen": "gi-lohen",
}


def public_candidate_report():
    registered = {r["id"]: r for r in source_coverage()["characters"]}
    if len(PROFILE_TO_SLUG) != 33 or len(set(PROFILE_TO_SLUG.values())) != 33:
        raise ValueError("Community source mapping count or uniqueness changed")
    rows = []
    for profile, slug in sorted(PROFILE_TO_SLUG.items()):
        if profile not in CHIBI_PROFILES or profile not in registered:
            raise ValueError("Public lead references an unknown roster profile: " + profile)
        pinned = registered[profile]["source_found"]
        rows.append({
            "profile": profile,
            "character": CHIBI_PROFILES[profile]["name"],
            "provider": "CodexPetDB Genshin community gallery",
            "candidate_url": "https://codexpetdb.com/en/pets/" + slug,
            "catalog_url": CATALOG_URL,
            "catalog_checked_date": CATALOG_DATE,
            "previously_pinned_creator_source": pinned,
            "new_unverified_lead_for_missing_character": not pinned,
            "source_asset_files_downloaded_and_hashed": False,
            "actual_artist_author_verified": False,
            "likeness_manually_reviewed": False,
            "distributable": False,
            "status": "candidate_unverified",
        })
    return {
        "scope": "manual_web_leads_not_approved_for_install",
        "summary": {
            "public_entries_in_collection": 35,
            "entries_mapped_to_roster": len(rows),
            "excluded_nonroster_variants": 2,
            "new_leads_for_previously_missing_characters": sum(
                x["new_unverified_lead_for_missing_character"] for x in rows),
            "pinned_source_coverage_is_unchanged": True,
            "added_to_installed_roles": 0,
            "art_likeness_approved": 0,
        },
        "characters": rows,
        "warning": ("Collection metadata and preview states do not prove visual likeness, "
                    "original author provenance, image integrity, actual availability "
                    "or permission to redistribute. Manually inspect each package first."),
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--new-leads-only", action="store_true")
    p.add_argument("--output", type=Path)
    args = p.parse_args(argv)
    result = public_candidate_report()
    if args.new_leads_only:
        result["characters"] = [r for r in result["characters"]
                                if r["new_unverified_lead_for_missing_character"]]
    content = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(content, encoding="utf-8")
    else:
        print(content, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

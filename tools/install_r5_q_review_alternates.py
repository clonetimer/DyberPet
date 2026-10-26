"""Stage two proven wider original Shimeji candidate variants for R5 review.

Does not substitute creator files or automatically select a 'Q approved' role.
Requires explicit consent. Installs only pinned Ayaka and Venti shimeji sources
into temporary directories, checks identity and original PNG geometry/motion,
then copies ONLY the new role folders beside existing original art. The current
63 distinct Genshin and two mascot profiles remain unchanged.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import tempfile
import os

from tools.install_artist_shimeji import install_artist_shimeji
from tools.creator_standee_triage import triage_one_creator
from tools.genshin_library import scan_genshin_library
from tools.mascot_library import scan_mascot_library

KNOWN = (("genshin_ayaka", "ayaka"), ("genshin_venti", "venti"))
EXPECTED = {"genshin_ayaka": "SourceShimejiAyaka",
            "genshin_venti": "SourceShimejiVenti"}


def stage_r5_original_alternatives(role_root, *, confirmed=False,
                                   install=None, measure=None):
    if not confirmed:
        raise ValueError("Explicit source download and personal-use consent required")
    root = Path(role_root).expanduser()
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Role root missing or linked")
    install = install or install_artist_shimeji
    measure = measure or triage_one_creator
    # This tool ONLY augments an existing R4 personal installation. It never
    # builds a partial replacement bundle or silently deletes earlier art.
    before = scan_genshin_library(root)
    mascots_before = scan_mascot_library(root)
    if (before["summary"]["personal_art_profile_count"] < 63 or
            mascots_before["summary"]["imported_creator_art_count"] != 2):
        raise ValueError("R4 personal 63 Genshin + two mascots base is required")
    if any((root / name).exists() or (root / name).is_symlink()
           for name in EXPECTED.values()):
        raise ValueError("An R5 creator source target already exists; never overwrite")
    checked = []
    with tempfile.TemporaryDirectory(prefix=".r5-real-art-",
                                     dir=str(root.parent)) as temp:
        staging = Path(temp) / "res" / "role"
        staging.mkdir(parents=True)
        for profile, slug in KNOWN:
            result = install(slug, staging, confirmed=True)
            expected = EXPECTED[profile]
            if result["profile"] != profile or result["folder"] != expected:
                raise ValueError("Alternate author art was associated to wrong identity")
            trial = scan_genshin_library(staging)
            row = next((x for x in trial["characters"] if x["profile"] == profile), None)
            if row is None or row["status"] != "structurally_installed":
                raise ValueError("Source did not yield native installed Genshin original art")
            measured = measure(staging, expected)
            if any("silhouette" in x for x in measured["risk_indicators"]):
                raise ValueError("Alternative still yields a high-narrow standee silhouette risk")
            if measured.get("weak_movement_action_evidence"):
                raise ValueError("Alternative has weak/repeated movement PNGs")
            checked.append({
                "profile": profile, "folder": expected,
                "silhouette_width_height_ratio": measured["silhouette_width_height_ratio"],
                "native_frame_source_original": True,
                "human_q_likeness_verified": False,
                "author_redistribution_rights_verified": False,
            })
        # All two fresh source packs have passed the original-data screen.
        for row in checked:
            target = root / row["folder"]
            if target.exists() or target.is_symlink():
                raise ValueError("Existing author art must never be overwritten")
        for row in checked:
            os.rename(staging / row["folder"], root / row["folder"])
    after = scan_genshin_library(root)
    mascots_after = scan_mascot_library(root)
    if (after["summary"]["personal_art_profile_count"] !=
            before["summary"]["personal_art_profile_count"] or
            mascots_after["summary"]["imported_creator_art_count"] != 2):
        raise ValueError("Unexpected distinct profile or mascot change")
    return {
        "scope": "opt-in_candidate_versions_only_not_chibi_approval",
        "additional_original_author_versions": len(checked),
        "unchanged_distinct_genshin_profiles": after["summary"]["personal_art_profile_count"],
        "unchanged_mascot_profiles": mascots_after["summary"]["imported_creator_art_count"],
        "original_sources": checked,
        "user_q_approved": 0,
        "overwrote_existing_source_art": False,
        "requires_user_frame_and_original_reference_review": True,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--role-root", required=True, type=Path)
    ap.add_argument("--accept-personal-use", action="store_true")
    ap.add_argument("--report", type=Path, required=True)
    args = ap.parse_args(argv)
    if args.report.exists() or args.report.is_symlink() or args.report.suffix.lower() != ".json":
        raise ValueError("Select a new, nonlinked .json report")
    result = stage_r5_original_alternatives(
        args.role_root, confirmed=args.accept_personal_use)
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print("R5_AYAKA_VENTI_ADDITIONAL_SOURCES="+str(result["additional_original_author_versions"]))


if __name__ == "__main__":
    main()

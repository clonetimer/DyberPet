#!/usr/bin/env python3
"""Read-only join of pinned creator sources, local sprites and native interactions.

This is a gap inventory, never evidence of artist likeness, gameplay quality,
character voice, rights, actual desktop playback or original-art approval.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

# Direct `python tools/creator_assistant_gap_report.py` must also find the
# project package, even when PYTHONPATH is not configured on Windows.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.character_source_coverage import source_coverage
from tools.character_interaction_coverage import interaction_coverage, _safe_installed_role
from tools.artist_animation_audit import audit_native_character

MASCOTS = frozenset(("mascot_guga", "mascot_doro"))


def _index_rows(report, *, key):
    result = {}
    for row in report["characters"]:
        identity = row[key]
        if not isinstance(identity, str) or not identity or identity in result:
            raise ValueError("Missing or repeated role ID in gap inventory")
        result[identity] = row
    return result


def _full_frame_structure(role_root, art, count):
    """Opt-in complete original PNG structure check, not character identity QA."""
    names = art.get("playable_creator_role_folders", [])
    if (not isinstance(names, list) or len(names) != count or
            any(not isinstance(name, str) for name in names) or
            len(names) != len(set(names))):
        raise ValueError("Creator-art inventory lacks exact per-folder evidence")
    results = []
    for name in names:
        try:
            role = _safe_installed_role(Path(role_root).expanduser(), name)
            inspected = audit_native_character(role)
            details = inspected["summary"]
            results.append({
                "folder": name,
                "status": ("structure_passed" if details["animation_structure_passed"]
                           else "structure_issues"),
                "frame_count": details["original_frames_inspected"],
                "problem_actions": details["actions_with_pixel_issues"],
                "issue_categories": details["issue_categories"],
            })
        except (ValueError, OSError, TypeError) as exc:
            # One broken installation does not conceal the state of other roles.
            results.append({
                "folder": name, "status": "structure_issues",
                "frame_count": 0, "problem_actions": None,
                "issue_categories": ["unreadable_or_incomplete_sequence"],
                "error": str(exc)[:160],
            })
    return results


def make_gap_report(role_root, *, pinned_report=None, installed_report=None,
                    deep_frame_audit=False):
    """Join reports by exact identity; no name guessing, downloads or writes."""
    sources = pinned_report if pinned_report is not None else source_coverage()
    local = installed_report if installed_report is not None else interaction_coverage(role_root)
    by_source = _index_rows(sources, key="id")
    by_local = _index_rows(local, key="id")
    if not by_source or any(not k.startswith("genshin_") for k in by_source):
        raise ValueError("Creator-source report contains invalid Genshin roster")
    expected = set(by_source) | MASCOTS
    if set(by_local) != expected:
        raise ValueError("Installed-art report does not match the full role roster")

    rows = []
    for identity in sorted(expected):
        source = by_source.get(identity, {})
        art = by_local[identity]
        pinned = bool(source.get("source_found", False))
        options = int(source.get("source_candidate_count", 0))
        if identity in by_source and (pinned != bool(options)):
            raise ValueError("Pinned creator-source counts are contradictory")
        folders = int(art.get("imported_creator_role_count", 0))
        usable_folders = int(art.get("playable_creator_role_count", 0))
        if not (0 <= usable_folders <= folders):
            raise ValueError("Creator-art folder counts are contradictory")
        first_frames = bool(art.get("original_creator_art_present", False))
        if first_frames != bool(usable_folders):
            raise ValueError("Creator-art first-frame receipt is inconsistent")
        if first_frames:
            stage = "local_creator_first_frame_decodable"
        elif folders:
            stage = "local_creator_files_unplayable"
        elif pinned:
            stage = "pinned_source_not_installed"
        else:
            stage = "missing_pinned_source"
        deep = (_full_frame_structure(role_root, art, usable_folders)
                if deep_frame_audit else [])
        deep_status = ("not_requested" if not deep_frame_audit else
                       "not_applicable" if not deep else
                       "passed_structure" if all(x["status"] == "structure_passed" for x in deep)
                       else "has_structure_issues")
        actions = list(art.get("action_categories_present_in_art", []))
        missing = list(art.get("action_categories_missing_in_art", []))
        if len(set(actions + missing)) != len(actions) + len(missing):
            raise ValueError("Duplicate or conflicting interaction categories")
        rows.append({
            "id": identity, "name": art["name"],
            "family": "mascot" if identity in MASCOTS else "genshin",
            "stage": stage,
            "pinned_source_known": pinned,
            "pinned_source_candidates": options,
            "imported_creator_folders": folders,
            "creator_folders_with_decodable_first_frames": usable_folders,
            "configured_actions_with_decodable_first_frame": list(art.get("actual_action_names", [])),
            "available_action_categories_in_art": actions,
            "missing_action_categories_in_art": missing,
            "local_asset_errors": list(art.get("errors", [])),
            "full_frame_structure_audit": {
                "status": deep_status,
                "checked_folder_count": len(deep),
                "folders": deep,
            },
            "human_original_likeness_verified": False,
            "complete_motion_sequence_verified": False,
            "physical_desktop_playback_verified": False,
            "voice_fidelity_verified": False,
            "rights_verified": False,
        })
    genshin = [x for x in rows if x["family"] == "genshin"]
    mascots = [x for x in rows if x["family"] == "mascot"]
    return {
        "scope": "offline_local_gap_inventory_not_acceptance",
        "summary": {
            "genshin_template_count": len(genshin),
            "mascot_template_count": len(mascots),
            "pinned_genshin_source_count": sum(x["pinned_source_known"] for x in genshin),
            "genshin_without_pinned_source": sum(not x["pinned_source_known"] for x in genshin),
            "genshin_with_decodable_creator_first_frame": sum(
                x["creator_folders_with_decodable_first_frames"] > 0 for x in genshin),
            "mascots_with_decodable_creator_first_frame": sum(
                x["creator_folders_with_decodable_first_frames"] > 0 for x in mascots),
            "roles_with_broken_local_creator_files": sum(
                x["stage"] == "local_creator_files_unplayable" for x in rows),
            "deep_frame_audit_enabled": bool(deep_frame_audit),
            "roles_with_full_frame_structure_checked": sum(
                x["full_frame_structure_audit"]["checked_folder_count"] > 0 for x in rows),
            "roles_with_full_frame_structure_issues": sum(
                x["full_frame_structure_audit"]["status"] == "has_structure_issues" for x in rows),
            "roles_with_all_checked_sequences_structurally_clean": sum(
                x["full_frame_structure_audit"]["status"] == "passed_structure" for x in rows),
            "human_likeness_approved": 0,
            "physical_desktop_qa_approved": 0,
            "voice_fidelity_approved": 0,
        },
        "roles": rows,
        "note": (
            "Pinned public sources are NOT installed art. The optional deep audit checks "
            "each available PNG sequence for decoding and structural issues. Neither "
            "first-frame checks nor this deep audit establish actual desktop playback, "
            "character identity, original likeness, "
            "voice, distribution rights or actual Windows/Linux GUI acceptance. "
            "Built-in demos never count as original creator art."
        ),
    }


def save_gap_report(destination, report):
    """Explicit atomic JSON export, without touching the role installation."""
    target = Path(destination)
    if target.suffix.lower() != ".json" or target.is_symlink() or target.is_dir():
        raise ValueError("Select a regular .json output path")
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", newline="\n", delete=False,
                dir=str(target.parent), prefix="." + target.name + ".", suffix=".tmp") as out:
            temp_path = Path(out.name)
            json.dump(report, out, ensure_ascii=False, indent=2)
            out.write("\n")
        os.replace(temp_path, target)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--role-root", type=Path,
                        default=Path(__file__).resolve().parents[1] / "res" / "role")
    parser.add_argument("--output", type=Path, help="Export UTF-8 JSON (read-only inputs)")
    parser.add_argument(
        "--deep-frame-audit", action="store_true",
        help="Opt-in slower full sprite sequence inspection; never certifies likeness")
    args = parser.parse_args(argv)
    report = make_gap_report(args.role_root, deep_frame_audit=args.deep_frame_audit)
    if args.output:
        save_gap_report(args.output, report)
    else:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Doro ONLY: strict, non-destructive completion gate for one Q版 character.

Never treat installed old Doro art, an animation preview, or a mirrored frame
as the user's accepted Dororong Live2D design. This does not fetch or
redistribute the 0x4682B4 model (whose reuse is restricted).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from .qchibi_threeview_audit import audit_role
    from .artist_motion_audit import audit_native_motion
except ImportError:
    from qchibi_threeview_audit import audit_role
    from artist_motion_audit import audit_native_motion

REFERENCE_URL = "https://booth.pm/zh-cn/items/5867617"
REFERENCE_CREATOR = "0x4682B4"
NECESSARY_ACTIONS = ("default", "left", "right", "patpat", "drag", "fall", "on_floor")
MAX_JSON = 128 * 1024
MAX_NAME = 128


def _receipt(folder, file):
    path = folder / file
    if (path.is_symlink() or not path.is_file()
            or path.stat().st_size > MAX_JSON):
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Doro evidence must be a JSON object")
    return data


def _approved_reference(source):
    """A URL is evidence of intent, not proof that its art was used legally."""
    if source is None:
        return False
    return (source.get("schema_version") == 1
            and source.get("character") == "Doro"
            and source.get("accepted_visual_reference") == REFERENCE_URL
            and source.get("accepted_visual_creator") == REFERENCE_CREATOR
            and source.get("body_type") == "quadruped"
            and isinstance(source.get("art_variant"), str)
            and 0 < len(source["art_variant"].strip()) <= MAX_NAME
            and source.get("art_variant") not in ("r7-classic", "demo")
            and isinstance(source.get("artist"), str)
            and 0 < len(source["artist"].strip()) <= MAX_NAME
            and source.get("not_a_legacy_approximation") is True)


def _review_pass(review):
    """All subjective evidence must be explicitly signed by a human."""
    if review is None or review.get("schema_version") != 1:
        return False
    flags = ("same_character_all_views", "original_character_likeness",
             "four_leg_gait", "native_interactions", "windows_real_desktop",
             "art_use_and_distribution_permission")
    return (all(review.get(key) is True for key in flags)
            and isinstance(review.get("reviewer"), str)
            and bool(review["reviewer"].strip())
            and isinstance(review.get("review_notes"), str)
            and bool(review["review_notes"].strip()))


def audit_doro(role_dir):
    """Return explicit blockers, not a misleading count of completed roles."""
    role = Path(role_dir).expanduser()
    output = {
        "role": "Doro", "expected_design": "0x4682B4 Dororong quadruped",
        "accepted_reference": REFERENCE_URL, "source_art_modified": False,
        "status": "blocked", "complete": False,
        "art_embedded_by_this_tool": False,
        "source_reference_recognized": False,
        "independent_threeview_candidate": False,
        "all_required_native_actions_bound": False,
        "manual_visual_and_windows_approved": False,
        "blockers": [],
    }
    errors = output["blockers"]
    if role.is_symlink() or not role.is_dir():
        errors.append("No real installed Doro role directory")
        return output

    try:
        source = _receipt(role, "DORO_SOURCE.json")
        if _approved_reference(source):
            output["source_reference_recognized"] = True
            output["artist"] = source["artist"]
            output["art_variant"] = source["art_variant"]
        else:
            errors.append("Missing approved Doro source lineage; R7 classic/Doro demo is NOT the accepted 0x4682B4 model")

        view = audit_role(role)
        output["threeview_evidence_status"] = view["status"]
        # File hashes + absence of copied/mirrored directions are NOT visual approval.
        if view["source_threeview_complete"]:
            output["independent_threeview_candidate"] = True
        else:
            errors.append("Missing three independently declared, valid source front/side/back PNG references")
        if view["status"] in ("invalid_role", "invalid_threeview_evidence",
                              "threeview_requires_source_correction"):
            errors.append("Invalid or suspicious native Q版 source references: "
                          + ";".join(view["issues"])[:180])

        try:
            motion = audit_native_motion(role)
            bound = motion["actions"]
            output["native_action_counts"] = {
                key: info["frames_in_source"] for key, info in bound.items()}
            missing = [x for x in NECESSARY_ACTIONS if x not in bound]
            motion_issues = [
                key for key in ("left", "right")
                if key in bound and bound[key]["visually_distinct_samples"] < 2
            ]
            if missing:
                errors.append("Missing real native action bindings: " + ",".join(missing))
            if motion_issues:
                errors.append("Four-foot movement frame sequence is static: "
                              + ",".join(motion_issues))
            for key in NECESSARY_ACTIONS:
                if key in bound and bound[key]["blank_samples"] > 0:
                    errors.append("Transparent empty samples in " + key)
            output["all_required_native_actions_bound"] = not (
                missing or motion_issues or
                any(key in bound and bound[key]["blank_samples"] > 0
                    for key in NECESSARY_ACTIONS))
            output["motion_warnings"] = motion["warnings"]
        except (ValueError, OSError, KeyError, TypeError) as exc:
            errors.append("Native artist animation cannot be validated: "
                          + str(exc)[:180])

        review = _receipt(role, "DORO_HUMAN_ACCEPTANCE.json")
        if _review_pass(review):
            output["manual_visual_and_windows_approved"] = True
        else:
            errors.append("Missing signed visual, four-foot gait, Windows desktop and distribution-rights review")
    except (ValueError, OSError, UnicodeError, json.JSONDecodeError) as exc:
        errors.append("Invalid Doro source or review receipt: " + str(exc)[:180])

    # Never auto-certify likeness; source checks alone cannot reach completion.
    if not errors and all((
        output["source_reference_recognized"],
        output["independent_threeview_candidate"],
        output["all_required_native_actions_bound"],
        output["manual_visual_and_windows_approved"]
    )):
        output["complete"] = True
        output["status"] = "accepted"
    return output


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--role", type=Path, required=True)
    parser.add_argument("--out", type=Path, help="Optional JSON report, not source PNG")
    parser.add_argument("--require-complete", action="store_true",
                        help="Fail closed: no Doro finished-product claim while any gate is pending")
    args = parser.parse_args(argv)
    report = audit_doro(args.role)
    data = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(data, encoding="utf-8")
    else:
        print(data, end="")
    return int(args.require_complete and not report["complete"])


if __name__ == "__main__":
    raise SystemExit(main())

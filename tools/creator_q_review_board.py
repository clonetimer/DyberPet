"""R5 original-creator Q-style comparison board (evidence, not character QA).

Aggregates actual locally installed original-art variants, bounded PNG shape/
motion risk measures and existing human review receipts. Never generates art,
modifies the active pet, labels a source as Q, or combines actions from
different variants.
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from tools.creator_standee_triage import triage_creator_library
from tools.creator_chibi_quality import summarize_local_quality
from tools.character_source_coverage import source_coverage
from tools.character_interaction_coverage import _safe_installed_role
from tools.artist_animation_audit import _read_config, _frames_for_action

MAX_VARIANTS = 500
MAX_CANDIDATES_PER_PROFILE = 12


def _first_artist_frame(root, folder):
    role = _safe_installed_role(Path(root).expanduser(), folder)
    if (role / "BUILTIN_CHIBI_DEMO.json").exists() or (role / "BUILTIN_MASCOT_DEMO.json").exists():
        raise ValueError("Built-in demos must not be displayed as original creator art")
    pet = _read_config(role / "pet_conf.json")
    actions = _read_config(role / "act_conf.json")
    default = pet.get("default")
    if not isinstance(default, str) or not isinstance(actions.get(default), dict):
        raise ValueError("No source-authored default action")
    frames = _frames_for_action(role, actions[default].get("images"))
    if not frames:
        raise ValueError("No native PNG default frame")
    return frames[0]


def make_review_board(role_root, *, measured=None, sources=None, quality=None):
    """Create one truthful per-version inspection board, sorted by review urgency.

    Measured/source/quality injections are strictly for headless tests. Runtime
    inputs are read-only and remain under the installation's res/role folder.
    """
    root = Path(role_root).expanduser()
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Original-art root missing or linked")
    evidence = measured if measured is not None else triage_creator_library(root)
    if evidence.get("scope") != "read_only_original_art_automated_review_priorities_not_likeness_grade":
        raise ValueError("Expected source original-art risk ledger")
    profiles = defaultdict(list)
    versions = evidence.get("versions")
    if not isinstance(versions, list) or len(versions) > MAX_VARIANTS:
        raise ValueError("Too many inventoried creator-art versions")
    for x in versions:
        if (not isinstance(x, dict) or
                not isinstance(x.get("id"), str) or
                not isinstance(x.get("folder"), str)):
            raise ValueError("Invalid original-art risk entry")
        _safe_installed_role(root, x["folder"])
        profiles[x["id"]].append(x["folder"])
    if len({x["folder"] for x in versions}) != len(versions):
        raise ValueError("The same imported folder cannot be counted twice")
    observed = quality if quality is not None else summarize_local_quality(root, profiles)
    pinned = sources if sources is not None else source_coverage()
    reference = {x["id"]: x for x in pinned["characters"]}
    if len(reference) != len(pinned["characters"]):
        raise ValueError("Duplicated source coverage profile")
    rows = []
    for item in versions:
        identity, folder = item["id"], item["folder"]
        reviewed = next((v for v in observed.get("profiles", {}).get(
            identity, {}).get("variants", []) if v.get("folder") == folder), {})
        visual_status = reviewed.get("status", "unreviewed_candidate")
        if visual_status == "user_q_standard_eligible" and not quality is None:
            # Test-injected data is not an independent human receipt.
            visual_status = "unreviewed_candidate"
        if visual_status not in (
            "user_q_standard_eligible", "unreviewed_candidate",
            "candidate_not_approved", "rejected_standee", "rejected_visual",
            "rejected_motion", "source_changed_recheck", "review_invalid"):
            visual_status = "review_invalid"
        source = reference.get(identity, {})
        options = list(source.get("source_candidates", []))
        if len(options) > MAX_CANDIDATES_PER_PROFILE:
            raise ValueError("Too many registered candidate sources")
        alternatives = [{
            "provider": x["provider"], "source_key": x["source_key"],
            "url": x["url"], "visual_verified": False,
        } for x in options]
        try:
            first_frame = _first_artist_frame(root, folder)
            frame_path = str(first_frame)
        except (OSError, ValueError, TypeError, KeyError):
            frame_path = None
        flags = item.get("risk_indicators", [])
        if not isinstance(flags, list) or any(not isinstance(f, str) for f in flags):
            raise ValueError("Invalid silhouette/motion evidence flags")
        high_and_thin = any("silhouette" in f for f in flags)
        weak_motion = bool(item.get("weak_movement_action_evidence", []))
        risk_priority = (4 if item["status"] == "unreadable_original_art" else
                         3 if high_and_thin and weak_motion else
                         2 if high_and_thin else 1 if weak_motion else 0)
        rows.append({
            "id": identity, "name": source.get("name", identity),
            "folder": folder, "first_png": frame_path,
            "human_q_status": visual_status,
            "risk_priority": risk_priority,
            "risk_is_not_a_q_style_verdict": True,
            "thin_silhouette_risk": high_and_thin,
            "weak_motion_risk": weak_motion,
            "silhouette_width_height_ratio": item.get("silhouette_width_height_ratio"),
            "weak_motion_details": list(item.get("weak_movement_action_evidence", [])),
            "source_options": alternatives,
            "available_source_option_count": len(alternatives),
            "human_likeness_still_required": True,
        })
    # Actual user-approved variants never get displaced by an unreviewed
    # candidate during a per-profile comparison, regardless of raw aspect.
    rows.sort(key=lambda x: (-x["risk_priority"], x["id"], x["folder"]))
    return {
        "scope": "local_read_only_artist_png_comparison_no_automatic_q_verdict",
        "summary": {
            "installed_artist_variants": len(rows),
            "distinct_installed_profiles": len(profiles),
            "thin_risk_versions": sum(r["thin_silhouette_risk"] for r in rows),
            "weak_motion_versions": sum(r["weak_motion_risk"] for r in rows),
            "personally_q_approved_versions": sum(
                r["human_q_status"] == "user_q_standard_eligible" for r in rows),
            "not_automatically_q_approved": True,
        },
        "rows": rows,
    }

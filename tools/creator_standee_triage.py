"""R4 evidence-only thin-standee silhouette and weak-motion risk triage.

This does NOT recognize the subject or decide whether artwork resembles a
specific game character. Tall silhouettes can be valid Q art and round
silhouettes can be a fake. Never assign a grade, overwrite artist pixels or
auto-admit a role to the approved/standard list using these heuristics.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

from PIL import Image, UnidentifiedImageError

from tools.artist_animation_audit import _read_config, _frames_for_action
from tools.character_interaction_coverage import _safe_installed_role

MAX_SIDE = 4096
MAX_PIXELS = 4_000_000
MAX_ROLE_VARIANTS = 500
MOTION_NAMES = ("left_walk", "right_walk", "walk", "run", "drag", "fall",
                "crawl", "climb", "jump")


def _frame_metrics(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 8 * 1024 * 1024:
        raise ValueError("Original PNG not a safe regular file")
    try:
        with Image.open(path) as img:
            if (img.format != "PNG" or img.width > MAX_SIDE or
                    img.height > MAX_SIDE or img.width * img.height > MAX_PIXELS):
                raise ValueError("Unacceptable sprite dimensions")
            img.load()
            rgba = img.convert("RGBA")
            box = rgba.getchannel("A").getbbox()
            if box is None:
                raise ValueError("Entire sprite transparent")
            x0, y0, x1, y1 = box
            width, height = x1 - x0, y1 - y0
            return {
                "bbox_width": width, "bbox_height": height,
                "opaque_bbox_width_height_ratio": round(width / max(height, 1), 4),
                "sprite_height_pixels": img.height,
                "sprite_width_pixels": img.width,
                "visual_content_sha256": hashlib.sha256(rgba.tobytes()).hexdigest(),
            }
    except (OSError, UnidentifiedImageError) as exc:
        raise ValueError("Unreadable PNG") from exc


def triage_one_creator(role_root, folder):
    root = Path(role_root).expanduser()
    role = _safe_installed_role(root, folder)
    if ((role / "BUILTIN_CHIBI_DEMO.json").exists() or
            (role / "BUILTIN_MASCOT_DEMO.json").exists()):
        raise ValueError("Demo/placeholder art is not creator-source material")
    actions = _read_config(role / "act_conf.json")
    pet = _read_config(role / "pet_conf.json")
    default = pet.get("default")
    if not isinstance(default, str) or default not in actions:
        raise ValueError("Missing original native default pose")
    original = _frames_for_action(role, actions[default].get("images"))
    if not original:
        raise ValueError("Missing default authored original PNG")
    visual = _frame_metrics(original[0])
    ratio = visual["opaque_bbox_width_height_ratio"]
    reasons = []
    # Extremely narrow/tall silhouettes are review PRIORITIES, never proof
    # of bad Q design. The two thresholds are deliberately conservative.
    if ratio < 0.44:
        reasons.append("extremely_thin_tall_silhouette_needs_human_review")
    elif ratio < 0.57:
        reasons.append("narrow_tall_silhouette_needs_human_review")
    weak_groups = []
    for name in MOTION_NAMES:
        if name not in actions or not isinstance(actions[name], dict):
            continue
        frames = _frames_for_action(role, actions[name].get("images"))
        if not frames:
            weak_groups.append({"action": name, "evidence": "missing_frames"})
            continue
        if len(frames) < 2:
            weak_groups.append({"action": name, "evidence": "single_frame_motion"})
            continue
        first = _frame_metrics(frames[0])["visual_content_sha256"]
        second = _frame_metrics(frames[1])["visual_content_sha256"]
        if first == second:
            weak_groups.append({"action": name, "evidence": "first_two_frames_identical"})
    if weak_groups:
        reasons.append("one_or_more_weak_movement_sequences")
    return {
        "folder": folder,
        "status": "review_priority" if reasons else "unverified_visual_candidate",
        "silhouette_width_height_ratio": ratio,
        "risk_indicators": reasons,
        "weak_movement_action_evidence": weak_groups,
        "sprite_measured": True,
        "human_chibi_likeness_qa": False,
        "rights_and_voice_verified": False,
        "not_a_pass_or_fail_classification": True,
        "auto_generated_standee_verdict": False,
    }


def triage_creator_library(role_root):
    from tools.genshin_library import scan_genshin_library
    from tools.mascot_library import scan_mascot_library
    root = Path(role_root).expanduser()
    genshin = scan_genshin_library(root)
    mascot = scan_mascot_library(root)
    identities = {}
    for role in genshin["characters"]:
        for entry in role["installed_folders"]:
            if not entry["is_original_demo"]:
                identities[entry["folder"]] = role["profile"]
    for role in mascot["mascots"]:
        for entry in role["imported_creator_art"]:
            identities[entry["folder"]] = "mascot_" + role["key"]
    if len(identities) > MAX_ROLE_VARIANTS:
        raise ValueError("Too many installed creator variants")
    results = []
    for folder, identity in sorted(identities.items()):
        try:
            item = triage_one_creator(root, folder)
            item["id"] = identity
            results.append(item)
        except (OSError, ValueError, TypeError, KeyError) as exc:
            results.append({"id": identity, "folder": folder, "status": "unreadable_original_art",
                            "risk_indicators": ["unreadable_or_incomplete_source"],
                            "reason": str(exc)[:130],
                            "human_chibi_likeness_qa": False,
                            "auto_generated_standee_verdict": False})
    return {
        "scope": "read_only_original_art_automated_review_priorities_not_likeness_grade",
        "summary": {
            "installed_variants_inspected": len(results),
            "silhouette_priority_count": sum(any(
                "silhouette" in risk for risk in x["risk_indicators"]) for x in results),
            "weak_motion_variant_count": sum(
                bool(x.get("weak_movement_action_evidence")) for x in results),
            "unreadable_variant_count": sum(
                x["status"] == "unreadable_original_art" for x in results),
            "automatically_approved_as_q": 0,
            "automatically_rejected_as_standee": 0,
        },
        "versions": results,
        "warning": "Tall/narrow shape and weak action differences are review leads only, never an automatic judgement about Q-style or original-game resemblance.",
    }

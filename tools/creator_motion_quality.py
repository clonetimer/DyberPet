"""R7 complete real-PNG motion evidence: no movement invented from canvas shifts.

Original PNG action frames are inspected *all the way through*, not merely
frames zero and one. Fully transparent padding does not count as a different
pose. Weak poses, long identical stretches, and motion composed only of moving
one rigid still image become per-action HUMAN REVIEW leads.

Read-only. This is not a semantic or official animation-quality classifier,
and must never autonomously reject/approve a creator's art.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from PIL import Image

from tools.artist_animation_audit import (
    MAX_ACTIONS, MAX_FRAMES_PER_ACTION, MAX_FRAME_BYTES, MAX_PIXELS, MAX_SIDE,
    MAX_TOTAL_FRAMES, MOVEMENT_NAMES, _frames_for_action, _read_config)
from tools.character_interaction_coverage import _safe_installed_role

# Idle/onfloor are legitimate authored still poses, not motion failures.
# Existing need_move metadata can elevate additional artist-specific actions.
MOTION_HINTS = MOVEMENT_NAMES


def _pose_signature(path):
    if (path.is_symlink() or not path.is_file() or
            path.stat().st_size > MAX_FRAME_BYTES):
        raise ValueError("Linked or oversized original PNG refused")
    with Image.open(path) as im:
        if (im.format != "PNG" or not 1 <= im.width <= MAX_SIDE or
                not 1 <= im.height <= MAX_SIDE or
                im.width * im.height > MAX_PIXELS):
            raise ValueError("Invalid original sprite size")
        im.load()
        pixels = im.convert("RGBA")
        bbox = pixels.getchannel("A").getbbox()
        if bbox is None:
            return None
        cropped = pixels.crop(bbox)
        # Include shape to avoid collisions across different-size drawings;
        # ignore *only* transparent margins / movement within the canvas.
        digest = hashlib.sha256(
            f"{cropped.width}x{cropped.height}:".encode("ascii") +
            cropped.tobytes()).hexdigest()
        return digest


def analyze_creator_actions(role_root, folder):
    root = Path(role_root).expanduser()
    role = _safe_installed_role(root, folder)
    if (role / "BUILTIN_CHIBI_DEMO.json").exists() or (
            role / "BUILTIN_MASCOT_DEMO.json").exists():
        raise ValueError("Generic demo art cannot be audited as an artist source")
    conf = _read_config(role / "act_conf.json")
    pet = _read_config(role / "pet_conf.json")
    if not conf or len(conf) > MAX_ACTIONS or pet.get("default") not in conf:
        raise ValueError("Missing native action definitions")
    result = []
    frame_count = 0
    cache = {}
    for action, spec in sorted(conf.items()):
        if not isinstance(action, str) or not isinstance(spec, dict):
            raise ValueError("Malformed action")
        frames = _frames_for_action(role, spec.get("images"))
        frame_count += len(frames)
        if frame_count > MAX_TOTAL_FRAMES or len(frames) > MAX_FRAMES_PER_ACTION:
            raise ValueError("Excessive author animation frames")
        if not frames:
            raise ValueError("Source action has no frames")
        signatures = []
        for path in frames:
            # Safe duplicate read of same PNG across action alias groups.
            if path not in cache:
                cache[path] = _pose_signature(path)
            signatures.append(cache[path])
        unique = len(set(signatures) - {None})
        longest, streak, prior = 0, 0, object()
        for signature in signatures:
            streak = (streak + 1 if signature == prior else 1)
            longest = max(longest, streak)
            prior = signature
        is_motion = (bool(spec.get("need_move")) or
                     action.casefold() in MOTION_HINTS)
        flags = []
        if None in signatures:
            flags.append("fully_transparent_frame")
        if is_motion and len(frames) == 1:
            flags.append("single_frame_motion")
        if is_motion and unique == 1 and len(frames) > 1:
            flags.append("translation_only_or_static_pose")
        if is_motion and len(frames) >= 4 and longest >= 3:
            flags.append("long_identical_pose_run")
        # Multiple poses means some appearance difference, NOT correct walking
        # or original-game identity. Avoid pretending otherwise.
        result.append({
            "action": action, "frame_count": len(frames),
            "unique_visible_poses": unique,
            "longest_identical_pose_run": longest,
            "movement_expected": is_motion,
            "risk_indicators": flags,
            "human_motion_verdict": "not_evaluated",
        })
    return {
        "folder": folder,
        "scope": "complete_original_png_pose_evidence_no_auto_q_or_motion_approval",
        "summary": {
            "actions_inspected": len(result),
            "frames_inspected": frame_count,
            "actions_with_motion_risk": sum(bool(x["risk_indicators"])
                                             for x in result),
            "all_frames_examined": True,
            "original_art_modified": False,
            "motion_semantics_approved": False,
        },
        "actions": result,
    }


def audit_installed_artist_motion(role_root):
    from tools.creator_standee_triage import triage_creator_library
    source = triage_creator_library(role_root)
    versions = source["versions"]
    results = []
    for src in versions:
        try:
            motion = analyze_creator_actions(role_root, src["folder"])
            row = {"id": src["id"], "folder": src["folder"],
                   "status": "read_only_analyzed",
                   "summary": motion["summary"], "actions": motion["actions"]}
        except (OSError, ValueError, TypeError, KeyError) as exc:
            row = {"id": src["id"], "folder": src["folder"],
                   "status": "unreadable_original_action",
                   "reason": str(exc)[:160], "actions": []}
        results.append(row)
    return {
        "scope": "all_installed_original_artist_pngs_r7_no_auto_visual_qa",
        "summary": {
            "artist_variants": len(results),
            "inspected_variants": sum(r["status"] == "read_only_analyzed"
                                     for r in results),
            "variants_with_pose_risk": sum(
                r["status"] == "read_only_analyzed" and
                r["summary"]["actions_with_motion_risk"] > 0 for r in results),
            "action_sequences_with_pose_risk": sum(
                r["summary"]["actions_with_motion_risk"]
                for r in results if r["status"] == "read_only_analyzed"),
            "unreadable_variants": sum(
                r["status"] != "read_only_analyzed" for r in results),
            "q_style_auto_approved": 0, "motion_auto_approved": 0,
        },
        "versions": results,
        "note": "Transparent-padding-normalized still poses are review leads, not judgments of art, character identity, natural motion or rights.",
    }

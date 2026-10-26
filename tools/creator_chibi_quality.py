"""R4 user-reviewed chibi (Q版) and standee quality gate.

Never infer human likeness from an aspect ratio or sprite checksum. A role is
recommended for the user's *local* standard shortlist ONLY when:
  - a human has reviewed original likeness, Q-style volume and every PNG frame;
  - the same human has checked action quality AND actual desktop playback;
  - a complete structural PNG audit finds no defect;
  - a snapshot of every relevant source PNG/config matches the saved receipt.

Receipts are saved in application data, NEVER next to creator's artwork, and
are deliberately NOT bundled into public software/source distributions.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from tempfile import NamedTemporaryFile
import os

from tools.character_interaction_coverage import _safe_installed_role
from tools.artist_animation_audit import _read_config, _frames_for_action, audit_native_character

FORM_CHOICES = ("未评价", "圆润Q版", "立牌/细长立绘", "其他不合格")
REVIEW_LIMIT = 256 * 1024
TOTAL_IMAGE_LIMIT = 512 * 1024 * 1024


def _review_location(role_root, folder):
    root = Path(role_root).expanduser()
    if root.is_symlink() or not root.is_dir() or root.name != "role" or root.parent.name != "res":
        raise ValueError("Selected role root must be the real res/role directory")
    _safe_installed_role(root, folder)
    folder_base = root.parent.parent / "data" / "creator_quality_reviews"
    if folder_base.is_symlink():
        raise ValueError("Review directory cannot be symlinked")
    return folder_base / (folder + ".json")


def _current_snapshot(role_root, folder):
    root = Path(role_root).expanduser()
    role = _safe_installed_role(root, folder)
    # Exact checksum contract of the existing manual frame-by-frame receipt.
    digest = hashlib.sha256()
    for name in ("act_conf.json", "pet_conf.json"):
        path = role / name
        if path.is_symlink() or not path.is_file() or path.stat().st_size > REVIEW_LIMIT:
            raise ValueError("Unsafe creator role configuration")
        digest.update(name.encode())
        digest.update(path.read_bytes())
    acts = _read_config(role / "act_conf.json")
    all_frames = {}
    for item in acts.values():
        if not isinstance(item, dict):
            raise ValueError("Malformed native action configuration")
        for png in _frames_for_action(role, item.get("images")):
            if png.is_symlink() or not png.is_file():
                raise ValueError("Unsafe creator original PNG")
            all_frames[png.name] = png
    total = 0
    for name, path in sorted(all_frames.items()):
        digest.update(name.encode())
        with path.open("rb") as stream:
            while block := stream.read(256 * 1024):
                total += len(block)
                if total > TOTAL_IMAGE_LIMIT:
                    raise ValueError("Original sprite set too large for local review")
                digest.update(block)
    return digest.hexdigest()


def evaluate_quality_receipt(role_root, folder, receipt, *, full_audit=True):
    """Read-only human + structural assessment for ONE imported sprite version."""
    if not isinstance(receipt, dict) or receipt.get("role_folder") != folder:
        return {"status": "review_invalid", "reason": "review_folder_mismatch"}
    qstyle = receipt.get("human_chibi_form", "未评价")
    if qstyle not in FORM_CHOICES:
        return {"status": "review_invalid", "reason": "invalid_q_style"}
    original = receipt.get("source_byte_snapshot_sha256")
    if not isinstance(original, str) or not re.fullmatch(r"[a-f0-9]{64}", original):
        return {"status": "review_invalid", "reason": "missing_source_snapshot"}
    try:
        current = _current_snapshot(role_root, folder)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        return {"status": "review_invalid", "reason": str(exc)[:130]}
    if current != original:
        return {"status": "source_changed_recheck", "reason": "creator_png_or_config_changed"}
    if qstyle in ("立牌/细长立绘", "其他不合格") or receipt.get("human_visual_grade") == "C 明显不符":
        return {"status": "rejected_standee" if qstyle == "立牌/细长立绘" else "rejected_visual",
                "reason": "human_rejected_chibi_or_likeness"}
    if (qstyle != "圆润Q版" or receipt.get("human_visual_grade") != "A 原设较吻合" or
            receipt.get("human_original_reference_compared") is not True or
            receipt.get("human_motion_review_confirmed") is not True or
            receipt.get("human_desktop_playback_checked") is not True):
        return {"status": "candidate_not_approved", "reason": "human_chibi_motion_or_desktop_review_missing"}
    frames = receipt.get("source_frames_by_action")
    if not isinstance(frames, dict) or not frames or not all(
        isinstance(x, dict) and x.get("every_frame_displayed") is True
        for x in frames.values()):
        return {"status": "candidate_not_approved", "reason": "original_frames_not_fully_reviewed"}
    if full_audit:
        role = _safe_installed_role(Path(role_root).expanduser(), folder)
        try:
            report = audit_native_character(role)
        except (OSError, ValueError, TypeError, KeyError) as exc:
            return {"status": "rejected_motion", "reason": str(exc)[:130]}
        if not report["summary"]["animation_structure_passed"]:
            return {"status": "rejected_motion",
                    "reason": ",".join(report["summary"]["issue_categories"])}
    else:
        # Never approve using metadata-only inspection.
        return {"status": "candidate_not_approved", "reason": "full_png_audit_required"}
    return {"status": "user_q_standard_eligible",
            "reason": "human_review_all_frames_plus_structural_audit",
            "official_likeness_or_rights_certified": False}


def load_local_quality_review(role_root, folder, *, full_audit=True):
    """Missing receipts remain candidates. Cannot silently endorse a creator."""
    location = _review_location(role_root, folder)
    if not location.exists():
        return {"status": "unreviewed_candidate", "reason": "no_human_q_review"}
    if location.is_symlink() or not location.is_file() or location.stat().st_size > REVIEW_LIMIT:
        return {"status": "review_invalid", "reason": "unsafe_review_file"}
    try:
        receipt = json.loads(location.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError, OSError):
        return {"status": "review_invalid", "reason": "malformed_review_json"}
    return evaluate_quality_receipt(role_root, folder, receipt, full_audit=full_audit)


def save_local_quality_review(role_root, folder, receipt):
    """Explicit user action only. Reject image changes; never overwrite art."""
    if not isinstance(receipt, dict) or receipt.get("role_folder") != folder:
        raise ValueError("Mismatch between selected role and review receipt")
    current = _current_snapshot(role_root, folder)
    if current != receipt.get("source_byte_snapshot_sha256"):
        raise ValueError("角色素材变化，必须重新预览后再保存Q版评审")
    # Do not accept synthetic approval for any review made without full frames.
    status = evaluate_quality_receipt(role_root, folder, receipt)
    if status["status"] in ("review_invalid", "source_changed_recheck"):
        raise ValueError("当前评审证据无效，无法保存")
    destination = _review_location(role_root, folder)
    if destination.is_symlink():
        raise ValueError("Cannot replace symlinked review")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.parent.is_symlink():
        raise ValueError("Linked review directory refused")
    text = json.dumps(receipt, ensure_ascii=False, indent=2) + "\n"
    if len(text.encode("utf-8")) > REVIEW_LIMIT:
        raise ValueError("Review receipt exceeds size bound")
    candidate = None
    try:
        with NamedTemporaryFile(mode="w", encoding="utf-8", dir=destination.parent,
                                 prefix="." + folder + ".", suffix=".tmp",
                                 delete=False) as stream:
            candidate = Path(stream.name)
            stream.write(text)
        os.replace(candidate, destination)
    finally:
        if candidate is not None:
            candidate.unlink(missing_ok=True)
    return status


def summarize_local_quality(role_root, profile_folders):
    """Group by exact installed version. Never claim entire character if no variant passed."""
    rows = {}
    for profile, folders in sorted(profile_folders.items()):
        versions = []
        for folder in folders:
            outcome = load_local_quality_review(role_root, folder)
            versions.append({"folder": folder, **outcome})
        statuses = {v["status"] for v in versions}
        classification = (
            "user_q_standard_eligible" if "user_q_standard_eligible" in statuses else
            "rejected_standee" if "rejected_standee" in statuses else
            "rejected_motion" if "rejected_motion" in statuses else
            "unreviewed_candidate")
        rows[profile] = {"status": classification, "variants": versions}
    return {"scope": "local_human_review_not_official_certification",
            "summary": {
                "installed_profiles": len(profile_folders),
                "user_q_standard_eligible": sum(
                    x["status"] == "user_q_standard_eligible" for x in rows.values()),
                "rejected_standee_profiles": sum(
                    x["status"] == "rejected_standee" for x in rows.values()),
                "rejected_motion_profiles": sum(
                    x["status"] == "rejected_motion" for x in rows.values()),
                "pending_or_unreviewed": sum(
                    x["status"] == "unreviewed_candidate" for x in rows.values()),
            }, "profiles": rows}

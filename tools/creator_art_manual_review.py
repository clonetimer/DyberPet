"""Local, explicitly user-authored creator-art visual and motion QA receipt.

Never mark a source likeness approved merely from frame decoding, QA coverage,
a model prediction or a downloaded archive checksum. Records are version-
scoped and retain a content snapshot hash of configuration + source PNG bytes,
so later file replacement can invalidate the prior human's observation.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from tools.character_interaction_coverage import _safe_installed_role

GRADES = ("未评价", "A 原设较吻合", "B 部分差异", "C 明显不符")
CHIBI_FORMS = ("未评价", "圆润Q版", "立牌/细长立绘", "其他不合格")
MAX_NOTE_LENGTH = 500
MAX_REVIEW_BYTES = 512 * 1024 * 1024  # bounded explicit, local-only review export


def create_manual_review_receipt(role_root, folder, inventory, visited, grade,
                                 compared_to_reference, motion_checked, notes="",
                                 chibi_form="未评价", desktop_checked=False):
    """Build a review report, never silently confer an official QA status."""
    role = _safe_installed_role(Path(role_root).expanduser(), folder)
    if not isinstance(inventory, dict) or not inventory:
        raise ValueError("本角色没有可核对的真实原生动画")
    if grade not in GRADES:
        raise ValueError("非法原设视觉评审级别")
    if not isinstance(compared_to_reference, bool) or not isinstance(motion_checked, bool):
        raise ValueError("人工确认字段必须明确勾选")
    if grade != "未评价" and not compared_to_reference:
        raise ValueError("评级前请确认已亲自对照角色原设形象")
    if chibi_form not in CHIBI_FORMS or not isinstance(desktop_checked, bool):
        raise ValueError("非法Q版体态/桌面播放评审状态")
    if chibi_form != "未评价" and not compared_to_reference:
        raise ValueError("判定Q版或立牌型前，必须亲自对照角色原设")
    if not isinstance(notes, str) or len(notes) > MAX_NOTE_LENGTH:
        raise ValueError("评审备注过长")
    frames = {}
    image_files = {}
    for action, paths in inventory.items():
        if not isinstance(action, str) or not isinstance(paths, list) or not paths:
            raise ValueError("动作证据格式错误")
        for p in paths:
            path = Path(p)
            if (path.is_symlink() or not path.is_file() or
                    path.parent != role / "action"):
                raise ValueError("检测到已失效或非法的原画路径")
            image_files[path.name] = path
        observed = visited.get(action, set())
        if (not isinstance(observed, (set, list, tuple)) or
                any(type(idx) is not int or idx < 0 or idx >= len(paths)
                    for idx in observed)):
            raise ValueError("人工审阅帧范围错误")
        frames[action] = {"source_frame_count": len(paths),
                          "frames_displayed_in_viewer": len(set(observed)),
                          "every_frame_displayed": len(set(observed)) == len(paths)}
    digest = hashlib.sha256()
    for config in ("act_conf.json", "pet_conf.json"):
        p = role / config
        if not p.is_file() or p.is_symlink():
            raise ValueError("素材配置已发生变化")
        digest.update(config.encode())
        digest.update(p.read_bytes())
    count = 0
    for name, path in sorted(image_files.items()):
        digest.update(name.encode())
        with path.open("rb") as fh:
            while part := fh.read(256 * 1024):
                count += len(part)
                if count > MAX_REVIEW_BYTES:
                    raise ValueError("需要复核的素材文件过大")
                digest.update(part)
    frame_total = sum(item["source_frame_count"] for item in frames.values())
    seen_total = sum(item["frames_displayed_in_viewer"] for item in frames.values())
    return {
        "schema": 1,
        "scope": "user_self_report_of_specific_installed_creator_version",
        "role_folder": folder,
        "source_byte_snapshot_sha256": digest.hexdigest(),
        "source_file_count": len(image_files),
        "source_frames_by_action": frames,
        "viewer_frame_coverage": {"displayed": seen_total, "total": frame_total},
        "human_original_reference_compared": compared_to_reference,
        "human_visual_grade": grade,
        "human_motion_review_confirmed": motion_checked,
        "human_chibi_form": chibi_form,
        "human_desktop_playback_checked": desktop_checked,
        "q_style_requires_manual_inspection": True,
        "human_note": notes.strip(),
        "original_game_identity_independently_verified": False,
        "official_art_approval": False,
        "voice_fidelity_verified": False,
        "reuse_rights_verified": False,
        "physical_desktop_playback_verified": False,
        "not_transferable_if_source_files_change": True,
        "note": ("本记录仅是本机用户自愿填写的逐版本观感反馈，不代表"
                 "官方美术认证、声线、版权或实际桌面验收通过。"),
    }


def save_manual_review(path, receipt, *, role_root):
    """Never overwrite installed original art, even if a user picks its folder."""
    target = Path(path)
    if target.suffix.lower() != ".json" or target.is_symlink():
        raise ValueError("仅允许保存为真实的 .json 文件，不覆盖符号链接")
    if target.resolve().is_relative_to(Path(role_root).resolve()):
        raise ValueError("评审报告不能写入原画素材安装目录")
    if not target.parent.is_dir():
        raise ValueError("报告导出目录不存在")
    payload = json.dumps(receipt, ensure_ascii=False, indent=2) + "\n"
    target.write_text(payload, encoding="utf-8")

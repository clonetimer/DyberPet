"""Non-destructive silhouette grounding and Q-chibi action consistency QA.

All pixels remain sourced from the installed author PNGs. Anchor calculation
uses alpha bounds for stable display, never rewrites/repaints a character.
Incomplete or suspicious artwork produces *review warnings*, not auto approval.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from PIL import Image, UnidentifiedImageError

try:
    from .role_action_preview import _png_dimensions, MAX_FRAME_BYTES
except ImportError:
    from role_action_preview import _png_dimensions, MAX_FRAME_BYTES

MAX_SAMPLES = 24
MAX_SOURCE_SIDE = 2048


def sample_frames(frames):
    """Bounded evenly spaced samples, preserving both ends."""
    if len(frames) <= MAX_SAMPLES:
        return tuple(frames)
    return tuple(frames[i * (len(frames) - 1) // (MAX_SAMPLES - 1)]
                 for i in range(MAX_SAMPLES))


def _visible(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_FRAME_BYTES:
        raise ValueError("Unsafe source PNG in Q-chibi pose geometry")
    _png_dimensions(path)
    try:
        with Image.open(path) as image:
            if image.format != "PNG":
                raise ValueError("Q-chibi pose geometry accepts original PNG only")
            if image.width > MAX_SOURCE_SIDE or image.height > MAX_SOURCE_SIDE:
                raise ValueError("Q-chibi source geometry is oversized")
            rgba = image.convert("RGBA")
            rgba.load()
            bbox = rgba.getchannel("A").getbbox()
            fingerprint = hashlib.sha256(rgba.tobytes()).hexdigest()
            return {
                "size": (rgba.width, rgba.height),
                "bbox": tuple(bbox) if bbox is not None else None,
                "hash": fingerprint,
                "fully_opaque": rgba.getchannel("A").getextrema() == (255, 255),
            }
    except (OSError, UnidentifiedImageError) as exc:
        raise ValueError("Unreadable source PNG in Q-chibi geometry") from exc


def _group(frames):
    sampled = sample_frames(frames)
    snapshots = [_visible(p) for p in sampled]
    bounds = [snap["bbox"] for snap in snapshots if snap["bbox"] is not None]
    if not bounds:
        raise ValueError("All source poses are empty transparent PNGs")
    rect = (min(b[0] for b in bounds), min(b[1] for b in bounds),
            max(b[2] for b in bounds), max(b[3] for b in bounds))
    return {
        "bbox_union": rect,
        "anchor": ((rect[0] + rect[2]) / 2, rect[3]),
        "visible_width": rect[2] - rect[0],
        "visible_height": rect[3] - rect[1],
        "sampled": len(snapshots),
        "different_poses": len({s["hash"] for s in snapshots}),
        "empty_frames": sum(s["bbox"] is None for s in snapshots),
        "opaque_samples": sum(s["fully_opaque"] for s in snapshots),
        "edge_touch_samples": sum(
            s["bbox"] is not None and
            (s["bbox"][0] == 0 or s["bbox"][1] == 0 or
             s["bbox"][2] == s["size"][0] or s["bbox"][3] == s["size"][1])
            for s in snapshots),
        "sampled_hashes": [s["hash"] for s in snapshots],
    }


def pose_geometry_for_role(plan):
    """Create fixed-scale display anchors and actionable advisories.

    Alignment is by the entire *action* silhouette union, not per-frame
    bounds. Thus original jump/bob within each animation is preserved.
    Three-view references use their own silhouette lower edge. Artwork
    scale is common to all and never inferred from transparent padding.
    """
    views = {}
    actions = {}
    warnings = []
    for key, item in plan["views"].items():
        if item["file"] is not None:
            views[key] = _group([item["file"]])
    for key, item in plan["interactions"].items():
        geometry = _group(item["frames"])
        actions[key] = geometry
        if geometry["empty_frames"]:
            warnings.append(key + "：存在透明空白动作帧")
        if key in ("left", "right") and len(item["frames"]) > 1 and geometry["different_poses"] <= 1:
            warnings.append(key + "：走路帧没有可见姿态变化")
        if geometry["edge_touch_samples"]:
            warnings.append(key + "：原画触及画布边缘，需检查裁切")
        if geometry["opaque_samples"] == geometry["sampled"]:
            warnings.append(key + "：动作帧全部不透明，可能存在背景底色")
    if "left" in actions and "right" in actions:
        if (plan["interactions"]["left"]["action"] ==
                plan["interactions"]["right"]["action"]):
            warnings.append("左右移动引用同一原生动作")
        if actions["left"]["sampled_hashes"] == actions["right"]["sampled_hashes"]:
            warnings.append("左右移动完全使用相同的可见帧")
    if "front" in views and "side" in views:
        heights = [views[k]["visible_height"] for k in ("front", "side")]
        if max(heights) / max(1, min(heights)) > 1.65:
            warnings.append("正面与侧面可见身高差异过大，可能混用版本或尺寸")
    if not plan.get("source_threeview_complete"):
        warnings.append("尚无同一造型的独立背面原画；不以镜像补图")
    measures = list(views.values()) + list(actions.values())
    if not measures:
        raise ValueError("No actual author Q-chibi poses")
    reference = (max(x["visible_width"] for x in measures),
                 max(x["visible_height"] for x in measures))
    return {
        "views": views,
        "interactions": actions,
        "reference_visible_dimensions": reference,
        "warnings": sorted(set(warnings)),
        "visual_quality_approved": False,
        "source_art_edited": False,
        "manual_review_required": True,
        "alpha_anchor_strategy": "union-per-action preserving native vertical movement",
    }

"""Conservative alignment and QA for small, top-heavy desktop sprites.

Never resize individual animation frames: only translate RGBA pixels within
their original transparent cell. Profile scale is applied by DyberPet itself.
"""
from __future__ import annotations

from statistics import median

GROUNDED = frozenset(("idle", "right_walk", "left_walk", "wave", "wait", "review", "run"))
STILL = frozenset(("idle", "wave", "wait", "review"))
CANVAS_W, CANVAS_H = 192, 208


def bbox(frame):
    return frame.getchannel("A").getbbox()


def offset_frame(frame, dx: int, dy: int):
    """Shift without clipping non-transparent pixels, or fail safely."""
    region = bbox(frame)
    if not region or (dx == 0 and dy == 0):
        return frame.copy()
    if region[0] + dx < 0 or region[2] + dx > frame.width:
        raise ValueError("horizontal shift would clip sprite")
    if region[1] + dy < 0 or region[3] + dy > frame.height:
        raise ValueError("vertical shift would clip sprite")
    from PIL import Image
    shifted = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    shifted.alpha_composite(frame, (dx, dy))
    return shifted


def normalize_grounded_frames(frames, max_shift=16):
    """Align grounded feet to the idle baseline.

    This intentionally avoids manipulating airborne jump/failed frames and
    avoids horizontal correction for walks (stride movement is significant).
    Returns (new_frames, applied_shift_counts, warnings).
    """
    original = frames.get("idle") or []
    grounded = [bbox(frame)[3] for frame in original if bbox(frame)]
    if not grounded:
        raise ValueError("idle animation has no opaque pixels")
    baseline = round(median(grounded))
    centered = [sum((r[0], r[2])) / 2 for frame in original
                if (r := bbox(frame))]
    center_x = round(median(centered)) if centered else CANVAS_W // 2
    result, shifts, warnings = {}, {}, []
    for action, animation in frames.items():
        corrected, changes = [], 0
        for index, frame in enumerate(animation):
            rect = bbox(frame)
            if not rect or action not in GROUNDED:
                corrected.append(frame.copy())
                continue
            requested_dy = baseline - rect[3]
            requested_dx = round(center_x - (rect[0] + rect[2]) / 2) if action in STILL else 0
            if abs(requested_dy) > max_shift:
                warnings.append(f"{action}[{index}]: ground drift {requested_dy}px exceeds {max_shift}px")
                requested_dy = 0
            if abs(requested_dx) > max_shift:
                warnings.append(f"{action}[{index}]: horizontal offset {requested_dx}px exceeds {max_shift}px")
                requested_dx = 0
            dx = max(-rect[0], min(frame.width - rect[2], requested_dx))
            dy = max(-rect[1], min(frame.height - rect[3], requested_dy))
            if (dx, dy) != (requested_dx, requested_dy):
                warnings.append(f"{action}[{index}]: shift limited to avoid frame clipping")
            fixed = offset_frame(frame, dx, dy)
            changes += int(bool(dx or dy))
            corrected.append(fixed)
        result[action] = corrected
        shifts[action] = changes
    return result, shifts, warnings


def suggested_scale(idle_frames, target_height=116, min_scale=0.55, max_scale=1.35):
    """Compute visible-height-based scale; avoid pathological tiny/huge art."""
    heights = [r[3] - r[1] for frame in idle_frames if (r := bbox(frame))]
    if not heights:
        raise ValueError("Idle frames are empty")
    raw = target_height / median(heights)
    scale = round(max(min_scale, min(max_scale, raw)), 3)
    return scale, abs(scale - raw) > 0.03


def quality_metrics(frames):
    return {
        state: {
            "frame_count": len(images),
            "visible_height_px": [
                (rect[3] - rect[1]) for image in images if (rect := bbox(image))
            ],
            "foot_baseline_px": [rect[3] for image in images if (rect := bbox(image))],
        }
        for state, images in frames.items()
    }

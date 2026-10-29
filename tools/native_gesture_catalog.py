"""Expose genuine artist-authored native gestures not already in pet's menu.

Pure functions: no download, art generation, editing, or file-system mutation.
Only loaded validated Act objects from PetConfig are considered eligible.
"""
from __future__ import annotations

import math

MAX_GESTURE_SECONDS = 45
MAX_FRAMES = 1200
MIN_FRAME_SECONDS = 0.015


def gesture_timing(act, tick_ms):
    """Return deterministic playback plan for a native authored Act."""
    images = getattr(act, "images", None)
    if not isinstance(images, (tuple, list)) or not images:
        return None
    try:
        count = int(getattr(act, "act_num", 1))
        seconds = float(getattr(act, "frame_refresh", 0))
        tick = float(tick_ms)
    except (ValueError, OverflowError, TypeError):
        return None
    if (count < 1 or count > 50 or len(images) > MAX_FRAMES
            or not math.isfinite(seconds) or not MIN_FRAME_SECONDS <= seconds <= 10
            or not math.isfinite(tick) or tick < 5 or tick > 200):
        return None
    duration = len(images) * count * seconds
    if duration > MAX_GESTURE_SECONDS or not math.isfinite(duration):
        return None
    # Floating-point 0.1 * 2 * 3 may yield 0.6000000000000001;
    # allow sub-nanotick rounding, never add a phantom last animation tick.
    ticks = max(1, math.ceil(duration * 1000 / tick - 1e-9))
    return {"frames": len(images), "repeats": count, "frame_seconds": seconds,
            "duration_seconds": round(duration, 2), "tick_ms": tick,
            "ticks": ticks}


def gesture_frame_index(tick_index, act, tick_ms):
    """Map elapsed scheduler ticks to the original author frame sequence."""
    plan = gesture_timing(act, tick_ms)
    if plan is None:
        raise ValueError("Unsafe or unavailable native gesture")
    if not isinstance(tick_index, int) or tick_index < 0:
        raise ValueError("Invalid authored gesture tick index")
    frame = min(
        plan["frames"] * plan["repeats"] - 1,
        math.floor(tick_index * plan["tick_ms"] /
                   (plan["frame_seconds"] * 1000)),
    )
    return frame % plan["frames"]


def native_gesture_catalog(config):
    """Return optional original actions absent from ordinary random/menu acts.

    Most roles do not expose all their hand-drawn actions in random_act.
    Filtering *by Act identity* avoids including idle/walk/petting core
    bindings under different original keys or duplicating existing menu acts.
    """
    actions = getattr(config, "act_dict", {})
    if not isinstance(actions, dict):
        return {}
    reserved = set()
    for name in ("default", "up", "down", "left", "right", "drag",
                 "fall", "prefall", "on_floor", "focus"):
        act = getattr(config, name, None)
        if act is not None:
            reserved.add(id(act))
    for act in getattr(config, "patpat", {}).values():
        reserved.add(id(act))
    for group in getattr(config, "random_act", ()):
        for act in group:
            reserved.add(id(act))
    for entry in getattr(config, "accessory_act", {}).values():
        for field in ("act_list", "acc_list"):
            for act in entry.get(field, ()):
                reserved.add(id(act))
    catalog = {}
    for key, act in actions.items():
        if not isinstance(key, str) or not key or len(key) > 80:
            continue
        if id(act) in reserved:
            continue
        timing = gesture_timing(act, getattr(config, "interact_speed", 20))
        if timing is None:
            continue
        # Only genuine author action frames already decoded by the native
        # Qt loader: never create a stand-in when a gesture is missing.
        catalog[key] = timing
    return dict(sorted(catalog.items(), key=lambda entry: entry[0].casefold()))

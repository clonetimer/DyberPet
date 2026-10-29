"""Mouse-click intent for real on-desktop character petting versus dragging.

Platform-independent, without Qt or images. A pixel of pointer jitter
must never turn a click/pat gesture into moving the entire desktop pet.
"""
from __future__ import annotations

import math

MIN_DRAG_PX = 6
MAX_DRAG_PX = 24
DEFAULT_DRAG_PX = 10


def drag_threshold(system_distance):
    """Honor the desktop accessibility preference, with safe bounds."""
    try:
        value = float(system_distance)
    except (TypeError, ValueError, OverflowError):
        return DEFAULT_DRAG_PX
    if not math.isfinite(value) or value <= 0:
        return DEFAULT_DRAG_PX
    return max(MIN_DRAG_PX, min(MAX_DRAG_PX, math.ceil(value)))


def deliberate_drag(start_x, start_y, now_x, now_y, threshold_px):
    """Only a true >= threshold movement may begin drag animation."""
    coords = (start_x, start_y, now_x, now_y)
    if any(not isinstance(x, (int, float)) or not math.isfinite(x) for x in coords):
        return False
    threshold = drag_threshold(threshold_px)
    dx, dy = now_x - start_x, now_y - start_y
    return dx * dx + dy * dy >= threshold * threshold

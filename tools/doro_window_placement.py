"""Screen-safe Doro desktop placement, independent of Qt and personal art.

Inputs/outputs are logical Qt desktop coordinates: (x, y, width, height).
Caller supplies the primary monitor FIRST, followed by other available screens.
"""
from __future__ import annotations


def _rect(item):
    if not isinstance(item, (list, tuple)) or len(item) != 4:
        return None
    try:
        values = tuple(int(v) for v in item)
    except (TypeError, ValueError, OverflowError):
        return None
    if values[2] <= 0 or values[3] <= 0:
        return None
    return values


def place_doro_window(saved_geometry, screens, default_size=(360, 370)):
    """Keep a stored position only if most of the pet remains on a live screen.

    After unplugging a monitor, recover near the bottom-right of the primary.
    Never make a pet permanently inaccessible with obsolete screen coordinates.
    """
    available = [_rect(screen) for screen in screens]
    available = [s for s in available if s]
    if not available:
        # Should not happen with a normal QApplication. Conservative fallback.
        return (40, 40, *default_size)

    saved = _rect(saved_geometry)
    primary = available[0]
    preferred_width = saved[2] if saved else default_size[0]
    preferred_height = saved[3] if saved else default_size[1]

    # Clamp to a usable size on the primary monitor, without exceeding the
    # original Doro QWidget minimum and without assuming 1080p.
    w = max(1, min(preferred_width, min(900, primary[2])))
    h = max(1, min(preferred_height, min(900, primary[3])))

    if saved:
        sx, sy, sw, sh = saved
        for x, y, screen_w, screen_h in available:
            intersection_w = max(0, min(sx + sw, x + screen_w) - max(sx, x))
            intersection_h = max(0, min(sy + sh, y + screen_h) - max(sy, y))
            if intersection_w * intersection_h >= (sw * sh * 0.6):
                local_w = max(1, min(preferred_width, min(900, screen_w)))
                local_h = max(1, min(preferred_height, min(900, screen_h)))
                return (
                    max(x, min(sx, x + screen_w - local_w)),
                    max(y, min(sy, y + screen_h - local_h)),
                    local_w, local_h,
                )

    px, py, pw, ph = primary
    return (px + max(0, pw - w - 24), py + max(0, ph - h - 24), w, h)

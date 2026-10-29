"""R47: stable in-memory Qt canvas for *real* installed author sprites.

Unlike R43/44 review-only tools, this is used by the live desktop PetWidget.
When native source frame canvases differ, draw each original QPixmap at a
shared visible-silhouette baseline, preserving a full action's authored
vertical motion. Never write, regenerate, mirror, or rescale source artwork
on disk; standard same-size source roles keep their untouched renderer.
"""
from __future__ import annotations

from collections import OrderedDict
import math

MAX_SOURCE_SIDE = 1536
MAX_FRAMES = 1600
MAX_RENDER_SIDE = 3072
MAX_CACHE = 8


def _alpha_rect(pixmap):
    """Visible alpha bounds of original frame; only evaluated once/role."""
    from PySide6.QtCore import QRect
    from PySide6.QtGui import QRegion
    if pixmap.isNull():
        return QRect()
    mask = pixmap.mask()
    if mask.isNull():
        return pixmap.rect()
    rect = QRegion(mask).boundingRect()
    return rect if not rect.isNull() else QRect()


class NativeSpriteCanvas:
    """A bounded-memory and transparent-background, stable desktop sprite."""

    def __init__(self, config):
        self.enabled = False
        self.width = max(1, round(float(config.width)))
        self.height = max(1, round(float(config.height)))
        self._anchors = {}
        self._recent = OrderedDict()
        self._default_anchor = None
        actions = getattr(config, "act_dict", {})
        if not isinstance(actions, dict):
            return
        unique = {}
        groups = []
        for action in actions.values():
            frames = getattr(action, "images", ())
            if not isinstance(frames, (tuple, list)) or not frames:
                continue
            group = []
            for frame in frames:
                if not hasattr(frame, "cacheKey") or frame.isNull():
                    continue
                if frame.width() > MAX_SOURCE_SIDE or frame.height() > MAX_SOURCE_SIDE:
                    return
                key = frame.cacheKey()
                unique[key] = frame
                group.append(frame)
                if len(unique) > MAX_FRAMES:
                    return
            if group:
                groups.append(group)
        if not unique:
            return
        dims = {(p.width(), p.height()) for p in unique.values()}
        # Existing original art uses its own intentional positions; do NOT
        # alter that workflow unless source frame canvases actually differ.
        if len(dims) == 1:
            return
        self.width = max(self.width, max(w for w, _ in dims))
        self.height = max(self.height, max(h for _, h in dims))
        if self.width > MAX_SOURCE_SIDE or self.height > MAX_SOURCE_SIDE:
            return

        visible = {key: _alpha_rect(pixmap) for key, pixmap in unique.items()}
        if all(rect.isNull() for rect in visible.values()):
            return
        # An action uses ONE union anchor for all its frames: do not erase
        # authored bob, hop, flight or squash-and-stretch per-frame offsets.
        for group in groups:
            rect = None
            for pixmap in group:
                current = visible[pixmap.cacheKey()]
                if current.isNull():
                    continue
                rect = current if rect is None else rect.united(current)
            if rect is None:
                continue
            anchor = (rect.x() + rect.width() / 2.0, rect.y() + rect.height())
            for pixmap in group:
                self._anchors.setdefault(pixmap.cacheKey(), anchor)

        if not self._anchors:
            return
        self._default_anchor = next(iter(self._anchors.values()))
        self.enabled = True

    def viewport(self, scale):
        value = float(scale)
        if not math.isfinite(value) or value <= 0:
            raise ValueError("Invalid sprite display scale")
        width, height = max(1, round(self.width * value)), max(1, round(self.height * value))
        if max(width, height) > MAX_RENDER_SIDE:
            raise ValueError("Source sprite display exceeds safe canvas size")
        return width, height

    def render(self, source, scale):
        """Return padded *display* pixmap; retains original pixel data intact."""
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QPainter, QPixmap
        if not self.enabled or source.isNull():
            return source
        width, height = self.viewport(scale)
        key = (source.cacheKey(), width, height)
        if key in self._recent:
            self._recent.move_to_end(key)
            return self._recent[key]
        scaled = source.scaled(
            max(1, round(source.width() * scale)),
            max(1, round(source.height() * scale)),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        anchor = self._anchors.get(source.cacheKey())
        if anchor is None:
            rect = _alpha_rect(source)
            anchor = (rect.x() + rect.width() / 2.0, rect.y() + rect.height())
        result = QPixmap(width, height)
        result.fill(Qt.GlobalColor.transparent)
        painter = QPainter(result)
        painter.drawPixmap(round(width / 2 - anchor[0] * scale),
                           round(height - anchor[1] * scale), scaled)
        painter.end()
        self._recent[key] = result
        if len(self._recent) > MAX_CACHE:
            self._recent.popitem(last=False)
        return result

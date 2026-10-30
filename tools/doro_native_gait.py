"""Doro creator-rig native Step controller (no artificial frames or mirroring).

The accepted Doro Cubism display info labels ParamStep as "Step". We do not
assume every edition has this parameter: unsupported models cannot walk.
The caller sends normalized step values to live2d.Model.SetParamById AFTER
Model.Update and BEFORE Model.Draw, then moves the Qt window on screen.
"""
from __future__ import annotations

import math


STEP_ID = "ParamStep"
SPEED_PX_PER_SEC = 72.0
CYCLE_HZ = 1.8
MAX_WALK_SECONDS = 5.0
BLEND_SECONDS = 0.28


class NativeStepGait:
    def __init__(self, minimum: float, maximum: float, default: float):
        values = (float(minimum), float(maximum), float(default))
        if not all(math.isfinite(v) for v in values):
            raise ValueError("Nonfinite Cubism step parameter")
        low, high, home = values
        if not low < high or not low <= home <= high:
            raise ValueError("Cubism Step parameter has no usable range")
        self.minimum, self.maximum, self.default = values
        self.value = home
        self.direction = 0
        self.remaining = 0.0
        self.phase = 0.0
        self.elapsed = 0.0

    @property
    def active(self) -> bool:
        return self.direction != 0 and self.remaining > 0

    def start(self, direction: int, seconds: float = 3.0) -> bool:
        if direction not in (-1, 1) or not math.isfinite(seconds) or seconds <= 0:
            return False
        # A left/right reversal is one continuous walk, not a fresh
        # animation. Preserve source Step phase and blend so feet do not
        # suddenly pop to home during an opposite-direction command.
        if not self.active:
            self.phase = -math.pi / 2
            self.elapsed = 0.0
        self.direction = direction
        self.remaining = min(float(seconds), MAX_WALK_SECONDS)
        return True

    def stop(self) -> None:
        self.direction = 0
        self.remaining = 0.0
        self.value = self.default
        self.elapsed = 0.0

    def tick(self, dt: float, x: float, left: float, right: float) -> float:
        """Advance source ParamStep and window position deterministically."""
        if not self.active:
            self.value = self.default
            return float(x)
        if not all(map(math.isfinite, (dt, x, left, right))):
            self.stop()
            return float(x) if math.isfinite(x) else 0.0
        dt = min(max(0.0, dt), 0.1, self.remaining)
        if right <= left:
            self.stop()
            return x
        next_x = max(left, min(right, x + self.direction * SPEED_PX_PER_SEC * dt))
        if abs(next_x - x) < 1e-8 and dt > 0:
            self.stop()
            return x
        self.phase += dt * (2 * math.pi * CYCLE_HZ)
        self.elapsed += dt
        remaining = max(0.0, self.remaining - dt)
        # Ease the author's real Step parameter in/out. The source default
        # need not be the midpoint (e.g. source may be 0..1, default 0).
        progress = min(1.0, self.elapsed / BLEND_SECONDS, remaining / BLEND_SECONDS)
        fade = progress * progress * (3.0 - 2.0 * progress)
        target = (self.minimum + self.maximum) / 2 + (
            (self.maximum - self.minimum) / 2 * math.sin(self.phase))
        self.value = self.default + fade * (target - self.default)
        self.remaining = remaining
        if self.remaining <= 1e-9 or (
                next_x <= left + 1e-8 and self.direction == -1) or (
                next_x >= right - 1e-8 and self.direction == 1):
            self.stop()
        return next_x


def source_step_gait(model):
    """Feature detection against the real native live2d-py SDK model."""
    ids = model.GetParamIds()
    if STEP_ID not in ids:
        return None
    try:
        return NativeStepGait(
            model.GetParamMinById(STEP_ID),
            model.GetParamMaxById(STEP_ID),
            model.GetParamDefaultById(STEP_ID),
        )
    except (TypeError, ValueError, OverflowError):
        return None

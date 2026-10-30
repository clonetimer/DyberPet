"""Subtle source-rig directional cue for the front-facing Doro Cubism model.

This does NOT provide side/back art. It uses an existing author-rig yaw
parameter (body preferred; head otherwise), and releases it after walking
so native idle motion can take control again. No art mirroring.
"""
from __future__ import annotations

import math

BODY_YAW = "ParamBodyAngleY"
HEAD_YAW = "ParamAngleY"
TURN_TIME = 0.24
RECOVERY_TIME = 0.30
MAX_TICK = 0.1


class NativeDirectionCue:
    def __init__(self, param_id, minimum, maximum, default):
        values = (float(minimum), float(maximum), float(default))
        if (param_id not in (BODY_YAW, HEAD_YAW)
                or not all(math.isfinite(v) for v in values)
                or not values[0] < values[1]
                or not values[0] <= values[2] <= values[1]):
            raise ValueError("Unsupported original Cubism yaw rig")
        self.param_id = param_id
        self.minimum, self.maximum, self.default = values
        self.value = self.default
        self.target = self.default
        self.state = "idle"

    @property
    def kind(self):
        return "body" if self.param_id == BODY_YAW else "head"

    @property
    def override(self):
        """None means the native Cubism animation owns this parameter."""
        if self.state == "idle":
            return None
        return self.param_id, self.value

    def start(self, direction):
        if direction not in (-1, 1):
            return False
        # Only a subtle, rig-supported facing cue; never pretend to show a
        # distinct side-view. Clamp around the model's OWN default value.
        fraction = 0.12 if self.kind == "body" else 0.09
        desired = self.default + direction * (self.maximum - self.minimum) * fraction
        self.target = max(self.minimum, min(self.maximum, desired))
        self.state = "turn"
        return True

    def release(self):
        if self.state == "idle":
            return
        self.target = self.default
        self.state = "recover"

    def cancel(self):
        self.value = self.default
        self.target = self.default
        self.state = "idle"

    def tick(self, dt):
        if self.state == "idle":
            return None
        if not isinstance(dt, (int, float)) or not math.isfinite(dt):
            self.cancel()
            return None
        dt = max(0.0, min(float(dt), MAX_TICK))
        duration = RECOVERY_TIME if self.state == "recover" else TURN_TIME
        # Rate-limited interpolation is frame-rate independent and keeps
        # reversed walks continuous rather than jumping across yaw limits.
        span = self.maximum - self.minimum
        maximum_delta = span * 0.20 * dt / duration
        delta = max(-maximum_delta, min(maximum_delta, self.target - self.value))
        self.value = max(self.minimum, min(self.maximum, self.value + delta))
        if self.state == "recover" and abs(self.value - self.default) <= 1e-7:
            self.cancel()
        return self.override


def source_direction_cue(model):
    """Discover only ranges from an actual loaded native Cubism model."""
    try:
        ids = set(model.GetParamIds())
    except (AttributeError, RuntimeError, TypeError):
        return None
    for param_id in (BODY_YAW, HEAD_YAW):
        if param_id not in ids:
            continue
        try:
            return NativeDirectionCue(
                param_id,
                model.GetParamMinById(param_id),
                model.GetParamMaxById(param_id),
                model.GetParamDefaultById(param_id),
            )
        except (AttributeError, RuntimeError, TypeError, ValueError, OverflowError):
            continue
    return None

"""Doro touch and gravity/landing actions driven by existing Cubism rig.

No sprites, no mirrored views, no authored motion files are invented. Petting
uses the source head parameter; landing uses source bounce/body parameters only
when these actually exist. The host Qt window supplies desktop coordinates.
"""
from __future__ import annotations
from dataclasses import dataclass
import math

HEAD = "ParamAngleZ"
BODY = "ParamBodyAngleZ"
BOUNCE = "ParamBounceInput1"
GRAVITY = 1700.0
MAX_DROP_TIME = 2.0
LAND_DURATION = 0.48
PAT_DURATION = 0.65


@dataclass(frozen=True)
class NativeRange:
    minimum: float
    maximum: float
    home: float

    def __post_init__(self):
        if (not all(math.isfinite(v) for v in
                    (self.minimum, self.maximum, self.home))
                or self.minimum >= self.maximum
                or not self.minimum <= self.home <= self.maximum):
            raise ValueError("Unusable source Cubism parameter")

    def scaled(self, amount: float):
        span = self.maximum - self.minimum
        return max(self.minimum, min(self.maximum, self.home + amount * span))


def read_source_ranges(model):
    """Only activate transforms the actual loaded author rig exposes."""
    ids = set(model.GetParamIds())
    ranges = {}
    for key in (HEAD, BODY, BOUNCE):
        if key not in ids:
            continue
        try:
            ranges[key] = NativeRange(
                float(model.GetParamMinById(key)),
                float(model.GetParamMaxById(key)),
                float(model.GetParamDefaultById(key)))
        except (ValueError, TypeError, OverflowError):
            continue
    return ranges


class DoroTouchDrop:
    def __init__(self, parameters=None):
        self.parameters = dict(parameters or {})
        self.phase = "idle"
        self.elapsed = 0.0
        self.y = 0.0
        self.floor_y = 0.0
        self.velocity = 0.0
        self.overrides = {}

    @property
    def active(self):
        return self.phase != "idle"

    def pat(self):
        self.phase = "pat"
        self.elapsed = 0.0
        self.overrides = {}
        return HEAD in self.parameters

    def drop(self, y, floor_y):
        if not (math.isfinite(y) and math.isfinite(floor_y)):
            return False
        self.y = min(float(y), float(floor_y))
        self.floor_y = float(floor_y)
        self.velocity = 0.0
        self.elapsed = 0.0
        self.overrides = {}
        self.phase = "fall" if self.y < self.floor_y - 1.0 else "land"
        return self.phase == "fall"

    def cancel(self):
        self.phase = "idle"
        self.elapsed = 0.0
        self.velocity = 0.0
        self.overrides = {}

    def tick(self, seconds):
        """Advance with deterministic bounded physics; returns window y."""
        if not self.active:
            self.overrides = {}
            return self.y
        if not math.isfinite(seconds):
            self.cancel()
            return self.y
        dt = min(0.08, max(0.0, float(seconds)))
        self.elapsed += dt
        values = {}
        if self.phase == "pat":
            progress = min(1.0, self.elapsed / PAT_DURATION)
            if HEAD in self.parameters:
                # A little nod; the original model deforms its own rig.
                values[HEAD] = self.parameters[HEAD].scaled(
                    0.14 * math.sin(2 * math.pi * progress) *
                    math.sin(math.pi * progress))
            if progress >= 1:
                self.cancel()
                return self.y
        elif self.phase == "fall":
            self.velocity = min(1800.0, self.velocity + GRAVITY * dt)
            self.y = min(self.floor_y, self.y + self.velocity * dt)
            if BODY in self.parameters:
                values[BODY] = self.parameters[BODY].scaled(-0.08)
            if self.y >= self.floor_y or self.elapsed >= MAX_DROP_TIME:
                self.y = self.floor_y
                self.velocity = 0.0
                self.phase = "land"
                self.elapsed = 0.0
        elif self.phase == "land":
            progress = min(1.0, self.elapsed / LAND_DURATION)
            # Dissipating impulses feed the creator's own bounce rig when
            # available; this is not a made-up author motion3 animation.
            impact = math.sin(3 * math.pi * progress) * (1 - progress)
            if BOUNCE in self.parameters:
                values[BOUNCE] = self.parameters[BOUNCE].scaled(0.3 * impact)
            elif BODY in self.parameters:
                values[BODY] = self.parameters[BODY].scaled(0.10 * impact)
            if progress >= 1:
                self.cancel()
                return self.y
        self.overrides = values
        return self.y

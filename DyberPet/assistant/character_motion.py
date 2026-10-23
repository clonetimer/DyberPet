"""Conservative desktop locomotion policy for Q-style characters.

No model, skeletal rig, sprite frames or voice assets are synthesized here.
Doro: faster ground movement when a native left/right sprite action exists.
Paimon: gentle *window-position* hover above the screen floor while idle.
Movement never grants unlocked animations and falls back to standard DyberPet
behavior for unknown characters and unsupported states.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

from .character_profiles import resolve_profile


@dataclass(frozen=True)
class MotionStyle:
    kind: str = "ground"
    horizontal_multiplier: float = 1.0
    hover_lift: int = 0
    bob_amplitude: int = 0
    bob_period: float = 2.4

    def bob_at(self, elapsed: float) -> int:
        if self.kind != "hover" or self.bob_amplitude <= 0:
            return 0
        elapsed = max(0.0, float(elapsed))
        # Loop starts and ends with zero offset; offset never increases y below
        # the configured hover plane.
        phase = 2 * math.pi * (elapsed % self.bob_period) / self.bob_period
        return -round(self.bob_amplitude * (1 - math.cos(phase)) / 2)

    def ground_lift(self, scale: float = 1.0) -> int:
        if self.kind != "hover":
            return 0
        scale = max(.5, min(2.0, float(scale)))
        return int(self.hover_lift * scale)

    def dx(self, dx: float, *, on_floor: bool, dragging: bool) -> float:
        if self.kind != "quadruped" or dragging or not on_floor:
            return dx
        # Apply only to real native sprite movement emitted by the worker;
        # we do not invent a four-leg gait from a static PNG.
        return dx * self.horizontal_multiplier


GROUND = MotionStyle()
DORO = MotionStyle(kind="quadruped", horizontal_multiplier=1.3)
PAIMON = MotionStyle(kind="hover", hover_lift=34, bob_amplitude=8, bob_period=2.4)


def style_for(character_name: str) -> MotionStyle:
    profile = resolve_profile(character_name)
    if profile is None:
        return GROUND
    if profile.key == "doro":
        return DORO
    if profile.key == "paimon":
        return PAIMON
    return GROUND

def is_authored_gait_frame(act, pet_conf, *, minimum_frames: int = 4) -> bool:
    """Recognize a true configured left/right Act with enough authored sprites.

    Never promote arbitrary jump/gesture displacement to quadruped movement.
    Counts distinct frame identities, not copies of one still frame.
    """
    if act is None or pet_conf is None:
        return False
    if act is not getattr(pet_conf, "left", None) and act is not getattr(pet_conf, "right", None):
        return False
    images = getattr(act, "images", None)
    if not isinstance(images, (list, tuple)) or len(images) < minimum_frames:
        return False
    if getattr(act, "direction", None) not in ("left", "right"):
        return False
    # DyberPet's current native Animation_worker moves on direction even when
    # legacy act_conf omits need_move. Match actual scheduler semantics.
    if not isinstance(getattr(act, "frame_move", None), (int, float)) or act.frame_move <= 0:
        return False
    ids = []
    for frame in images:
        # Qt's QPixmap.cacheKey identifies real backing buffers; for synthetic
        # test objects object id is adequate. Never compare QPixmap pixels here.
        key = frame.cacheKey() if hasattr(frame, "cacheKey") else id(frame)
        ids.append(key)
    return len(set(ids)) >= minimum_frames

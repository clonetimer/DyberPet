"""Safe screen-space hover for DyberPet mini-pets (res/pet).

The main-role PetWidget is a different runtime. This controller only corrects
an independently floor-following mini-pet's *window Y position*. It does not
replace sprite animation, main-character following, mouse drag or physics.
"""
from __future__ import annotations

from dataclasses import dataclass
from .character_motion import style_for


@dataclass(frozen=True)
class MiniHover:
    enabled: bool = False
    base_lift_px: int = 0
    bob_period: float = 2.4
    max_step_px: int = 4

    @classmethod
    def for_pet(cls, character_name: str, *, is_subpet: bool,
                follows_main_y: bool, enabled: bool = True):
        style = style_for(character_name)
        # Follow-main-y characters already have a dedicated vertical target.
        # Do not compete with the original main-follow animation.
        if not (is_subpet and enabled and
                style.kind == "hover" and not follows_main_y):
            return cls()
        return cls(enabled=True, base_lift_px=style.hover_lift,
                   bob_period=style.bob_period)

    def next_y(self, current_y: int, floor_y: int, seconds: float,
               scale: float = 1.0) -> int:
        if not self.enabled:
            return int(current_y)
        style = style_for("paimon")
        base = int(floor_y) - style.ground_lift(scale)
        # Uses the same periodic bob as the main-role implementation. The
        # absolute target prevents cumulative Y drift across thousands of ticks.
        target = base + style.bob_at(seconds)
        delta = max(-self.max_step_px,
                    min(self.max_step_px, target - int(current_y)))
        return int(current_y) + delta

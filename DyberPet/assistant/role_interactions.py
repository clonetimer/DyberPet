"""Per-character action mapping without fabricating frames or unlocking assets.

Only actions reported by the currently active PetWidget are eligible.
This is a *manual* interaction convenience, never a model/tool side effect.
"""
from __future__ import annotations

# Friendly choices for artist-imported Codex sprites, Shimeji conversions and
# legacy DyberPet Chinese action-group names. All matches are full exact names.
INTERACTION_CATEGORIES = (
    ("greet", "打招呼", ("打招呼", "招手", "挥手", "wave", "hello", "greet")),
    ("jump", "蹦一蹦", ("蹦一蹦", "跳跃", "跳一跳", "jump", "happy", "bounce")),
    ("observe", "观察周围", ("认真观察", "左顾右盼", "观察", "lookaround", "review", "focus")),
    ("rest", "休息一下", ("休息", "等待", "稍作休息", "wait", "rest", "idle")),
    ("walk", "散步", ("左右散步", "散步", "行走", "walk", "right_walk", "left_walk", "run")),
    ("talk", "说话动作", ("说话", "口型", "对话", "talk", "speak")),
    ("sleep", "睡觉", ("睡觉", "睡眠", "sleep", "nap")),
    ("pet", "摸摸头", ("抚摸", "摸头", "拍拍", "patpat", "pat", "pet")),
    ("climb", "爬行", ("攀爬", "爬墙", "climb", "climbing")),
)


def available_interactions(unlocked_actions):
    """Return deterministic affordances; missing actions stay disabled.

    Do not guess action semantics by substring or choose an unrelated fallback.
    """
    allowed = {
        name.casefold(): name for name in unlocked_actions
        if isinstance(name, str) and name and name == name.strip()
    }
    result = []
    for kind, label, aliases in INTERACTION_CATEGORIES:
        match = next((allowed[k.casefold()] for k in aliases
                      if k.casefold() in allowed), None)
        result.append({"id": kind, "label": label,
                       "action": match, "available": match is not None})
    return result


def requested_action(interactions, category):
    """Refuse missing/unknown categories, caller validates at dispatch again."""
    for entry in interactions:
        if entry["id"] == category:
            return entry["action"] if entry["available"] else None
    return None

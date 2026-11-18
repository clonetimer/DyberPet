"""Choose a proven silent native clip for one listening/thinking phase entry.

The action menu metadata does not contain the sound used by the native engine.
Interaction_worker.start_interact reads PetConfig.act_sound for random actions,
so silence must be established from that loaded resource, not a missing or
invented field in allAct_params. Other action families fail closed to a bubble.
"""
from __future__ import annotations

from math import isfinite


_PHASE_NAMES = {
    "listening": {
        "listen", "listening", "listenloop", "listeningloop",
        "倾听", "聆听", "监听", "倾听动作", "聆听动作", "监听动作",
    },
    "thinking": {
        "think", "thinking", "thinkloop", "thinkingloop",
        "思考", "想一想", "思考动作",
    },
}


def _renderable(clip):
    images = getattr(clip, "images", None)
    refresh = getattr(clip, "frame_refresh", None)
    repeats = getattr(clip, "act_num", None)
    if (not isinstance(images, (list, tuple)) or not images
            or not isinstance(refresh, (int, float))
            or not isfinite(refresh) or refresh <= 0
            or not isinstance(repeats, int) or repeats <= 0):
        return False
    for frame in images:
        if frame is None:
            return False
        is_null = getattr(frame, "isNull", None)
        if callable(is_null) and is_null():
            return False
    return True


def available_interaction_action(action_config, pet_conf, phase, *, hp_tier):
    """Return an unlocked, loaded random action with an explicit empty sound list.

    Native random actions are the bounded, main-pet-only resource path verified
    here. Accessory and customized actions are intentionally left to the existing
    manual controls; automatic voice feedback uses the existing bubble instead.
    """
    names = _PHASE_NAMES.get(phase)
    if (names is None or not isinstance(action_config, dict)
            or not isinstance(hp_tier, int) or isinstance(hp_tier, bool)):
        return None
    loaded_names = getattr(pet_conf, "act_name", None)
    if not isinstance(loaded_names, (list, tuple)):
        return None
    for name, config in action_config.items():
        if (not isinstance(name, str) or not isinstance(config, dict)
                or config.get("unlocked") is not True
                or config.get("act_type") != "random_act"
                or config.get("special_act")):
            continue
        normalized = "".join(c for c in name.casefold().strip()
                             if c not in "-_ \t")
        if normalized not in names or loaded_names.count(name) != 1:
            continue
        index = loaded_names.index(name)
        try:
            sounds = pet_conf.act_sound[index]
            clips = pet_conf.random_act[index]
            minimum_hp = pet_conf.act_type[index][0]
        except (AttributeError, IndexError, KeyError, TypeError):
            continue
        if (not isinstance(sounds, (list, tuple)) or sounds
                or not isinstance(minimum_hp, int)
                or not 0 <= minimum_hp <= hp_tier
                or not isinstance(clips, (list, tuple)) or not clips):
            continue
        if not all(_renderable(clip) for clip in clips):
            continue
        return name
    return None

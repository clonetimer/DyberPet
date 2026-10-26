"""Choose only an installed, unlocked native *talk* action.

This is a speech-start gesture, not phoneme or amplitude lip-sync. Do not
fabricate sprite frames or infer a dialogue action from arbitrary names.
"""
from __future__ import annotations

_ALLOWED = {
    "talk", "talking", "speak", "speaking", "speech",
    "say", "dialogue", "dialog", "talkloop", "speakloop",
    "说话", "讲话", "对话", "说话动作", "讲话动作", "口型",
}


def _normalize(name: str) -> str:
    return "".join(c for c in name.casefold().strip() if c not in "-_ \t")


def available_talk_action(action_config: dict, *, playable_groups=None) -> str | None:
    """Select only an unlocked speech-group, optionally intersecting PetWidget.

    A group with "talk" in its name is not necessarily playable by the
    engine's "actlist" channel; only current native random_act groups can
    be used for live TTS gestures.
    """
    if not isinstance(action_config, dict):
        return None
    for name, config in action_config.items():
        if (isinstance(name, str) and isinstance(config, dict)
                and config.get("unlocked") is True
                and config.get("act_type") in (
                    "random_act", "customized", "accessory_act")
                and _normalize(name) in _ALLOWED
                and (playable_groups is None or name in playable_groups)):
            return name
    return None

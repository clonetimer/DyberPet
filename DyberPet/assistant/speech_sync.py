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


def available_talk_action(action_config: dict) -> str | None:
    """Select only an already unlocked user-visible native action."""
    if not isinstance(action_config, dict):
        return None
    for name, config in action_config.items():
        if (isinstance(name, str) and isinstance(config, dict)
                and config.get("unlocked") is True
                and config.get("act_type") in (
                    "random_act", "customized", "accessory_act")
                and _normalize(name) in _ALLOWED):
            return name
    return None

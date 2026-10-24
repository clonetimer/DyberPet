"""Choose imported Blender NLA clips for DyberPet animation actions.

Pure standard library; Blender 4.0 and 4.4+ glTF imports may place actions on
multiple NLA tracks of the same name, one per animated object. We select a
clip NAME here; the renderer then unmutes all matching tracks together.
"""
from __future__ import annotations
import re

ALIASES = {
    "idle": ("idle", "standing", "stand", "breathing"),
    "left_walk": ("left_walk", "walk_left", "leftwalk", "walkleft"),
    "right_walk": ("right_walk", "walk_right", "rightwalk", "walkright"),
    "wave": ("wave", "waving", "greet", "hello"),
    "jump": ("jump", "jumping"),
    "wait": ("wait", "waiting", "rest"),
    "sleep": ("sleep", "sleeping"),
    "review": ("review", "working", "focus"),
}

def normalize(name):
    """Normalize names but retain meaningful direction/role distinctions."""
    return re.sub(r"[^a-z0-9]+", "_", name.casefold()).strip("_")


def choose_clips(actions, available, overrides=None):
    """Return action -> clip name, with explicit override or conservative aliases.

    Track names may be duplicated on different objects; this is expected.
    A single track name cannot silently supply unrelated actions.
    """
    overrides = overrides or {}
    if set(overrides).difference(actions):
        raise ValueError("Clip mapping contains actions that were not requested")
    names = {}
    for name in available:
        token = normalize(name)
        if not token:
            continue
        names.setdefault(token, set()).add(name)
    mapped = {}
    used = set()
    for action in actions:
        options = ([normalize(overrides[action])] if action in overrides
                   else [normalize(x) for x in ALIASES[action]])
        exact = options[0] if options else ""
        found = names.get(exact, set())
        if not found:
            for alias in options[1:]:
                if names.get(alias):
                    found = names[alias]
                    break
        if not found:
            continue
        if len(found) != 1:
            raise ValueError("Ambiguous NLA track names for " + action)
        choice = next(iter(found))
        if choice in used:
            raise ValueError("One NLA clip cannot be assigned to multiple actions")
        mapped[action] = choice
        used.add(choice)
    return mapped

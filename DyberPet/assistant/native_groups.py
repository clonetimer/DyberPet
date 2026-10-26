"""Bridge native act_conf sprites to the *group names* accepted by PetWidget.

The running Interaction worker plays "actlist" group names, not individual
wave/jump frame names. Never invent or unlock group names from file labels.
"""
from __future__ import annotations

import json
from pathlib import Path
from .role_interactions import available_interactions


def _category_for(name):
    yes = [x["id"] for x in available_interactions([name]) if x["available"]]
    return yes[0] if len(yes) == 1 else None


def playable_runtime_group_names(options, groups, loaded_native_names):
    """Action groups PetWidget can actually execute, not individual PNG keys.

    Accept non-semantic miscellaneous animations for the direct action menu,
    but never accept an accessory/custom action or any group whose native
    references are missing. The 12 semantic shortcuts use a tighter subset.
    """
    if not isinstance(options, dict) or not isinstance(groups, list):
        return frozenset()
    native = {x for x in loaded_native_names if isinstance(x, str)}
    ready = set()
    for group in groups[:128]:
        if not isinstance(group, dict):
            continue
        name, refs = group.get("name"), group.get("act_list")
        if (not isinstance(name, str) or not name or
                not isinstance(refs, list) or not 1 <= len(refs) <= 8 or
                not all(isinstance(x, str) and x in native for x in refs)):
            continue
        state = options.get(name)
        if (isinstance(state, dict) and state.get("unlocked") is True
                and state.get("act_type") == "random_act"):
            ready.add(name)
    return frozenset(ready)


def runtime_group_interactions(options, groups, loaded_native_names):
    """Strictly map unlocked action groups to coherent native animation categories."""
    empty = available_interactions([])
    if not isinstance(options, dict) or not isinstance(groups, list):
        return empty
    ready = playable_runtime_group_names(options, groups, loaded_native_names)
    chosen = {}
    for group in groups[:128]:
        if not isinstance(group, dict):
            continue
        title, refs = group.get("name"), group.get("act_list")
        if not isinstance(title, str) or title not in ready:
            continue
        meanings = [_category_for(x) for x in refs]
        if not meanings[0] or any(x != meanings[0] for x in meanings):
            continue
        category = meanings[0]
        declared = _category_for(title)
        if declared is not None and declared != category:
            continue
        chosen.setdefault(category, title)
    return [{**entry, "action": chosen.get(entry["id"]),
             "available": entry["id"] in chosen} for entry in empty]


def _read_runtime_groups(role_root, role_name):
    """Read current selected local role only, never following linked configuration."""
    root = Path(role_root).expanduser()
    if (root.is_symlink() or not isinstance(role_name, str) or
            not 1 <= len(role_name) <= 120 or role_name in (".", "..") or
            any(x in role_name for x in ("/", chr(92), chr(0)))):
        raise ValueError("Invalid current role name/root")
    role = root / role_name
    config_path = role / "pet_conf.json"
    if (role.is_symlink() or config_path.is_symlink() or
            not config_path.is_file() or config_path.stat().st_size > 262144):
        raise ValueError("No safe current role action-group configuration")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError("Native role configuration must be an object")
    return config.get("random_act")


def load_runtime_group_snapshot(role_root, role_name, options, loaded_native_names):
    """Single filesystem snapshot for action menu AND just-in-time dispatch."""
    groups = _read_runtime_groups(role_root, role_name)
    return (
        playable_runtime_group_names(options, groups, loaded_native_names),
        runtime_group_interactions(options, groups, loaded_native_names),
    )


def load_runtime_group_interactions(role_root, role_name, options, loaded_native_names):
    """Compatibility helper for audit/read-only callers."""
    return load_runtime_group_snapshot(
        role_root, role_name, options, loaded_native_names)[1]

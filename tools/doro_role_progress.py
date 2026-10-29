"""Doro's own interaction progress inside DyberPet's *existing* PetData save.

A Live2D-only role must not replace the active sprite PetConfig or mutate
the hidden sprite's HP/FV. This adapter uses the same PetData instance and
pet_data.json writer, but a reserved per-role entry for Doro interactions.
No separate save file, background task, or synthetic animation is created.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime

ROLE_KEY = "Doro Live2D"
ACTIONS = ("pat", "walk_left", "walk_right", "drop", "land")
_COUNTERS_KEY = "doro_interactions"
_MAX_COUNTER = 2**31 - 1


def _new_profile(today=None):
    today = today or datetime.now()
    return {
        "HP": -1, "HP_tier": 3,
        "FV": 0, "FV_lvl": 0, "fv_sys_ver": "v2",
        "items": {}, "coins": 0,
        "days": 1,
        "last_opened": f"{today.year}-{today.month}-{today.day}",
        _COUNTERS_KEY: {name: 0 for name in ACTIONS},
    }


def _owner(pet_data):
    return (pet_data is not None
            and not getattr(pet_data, "frozen_data", False)
            and isinstance(getattr(pet_data, "allData_params", None), dict)
            and callable(getattr(pet_data, "save_data", None)))


def _normalized(existing):
    """Keep the original role schema, sanitize only our own counters."""
    if not isinstance(existing, dict):
        return None
    record = deepcopy(existing)
    raw = record.get(_COUNTERS_KEY, {})
    if not isinstance(raw, dict):
        raw = {}
    record[_COUNTERS_KEY] = {
        name: (value if type(value) is int and 0 <= value <= _MAX_COUNTER else 0)
        for name in ACTIONS
        for value in [raw.get(name, 0)]
    }
    return record


def ensure_doro_profile(pet_data):
    """Create only after model load, never change pet_data.current_pet."""
    if not _owner(pet_data):
        return None
    original = pet_data.allData_params.get(ROLE_KEY)
    profile = _new_profile() if original is None else _normalized(original)
    if profile is None:
        return None  # Don't overwrite an unknown incompatible prior record.
    if original != profile:
        pet_data.allData_params[ROLE_KEY] = profile
        pet_data.save_data()
    return deepcopy(profile)


def record_doro_action(pet_data, action):
    """Write exactly one recognized discrete interaction using PetData."""
    if action not in ACTIONS or not _owner(pet_data):
        return False
    # Do not create entries before the source model has loaded.
    if ROLE_KEY not in pet_data.allData_params:
        return False
    current = pet_data.allData_params[ROLE_KEY]
    normalized = _normalized(current)
    if normalized is None:
        return False
    count = normalized[_COUNTERS_KEY][action]
    if count == _MAX_COUNTER:
        return False
    normalized[_COUNTERS_KEY][action] = count + 1
    pet_data.allData_params[ROLE_KEY] = normalized
    pet_data.save_data()
    return True


def doro_progress(pet_data):
    """Return an isolated read-only snapshot; never touch ordinary-role data."""
    if pet_data is None:
        return None
    source = getattr(pet_data, "allData_params", None)
    if not isinstance(source, dict) or ROLE_KEY not in source:
        return None
    record = _normalized(source[ROLE_KEY])
    return (deepcopy(record[_COUNTERS_KEY]) if record is not None else None)

"""Doro-only status and real completed-task credits.

Stored under the existing Doro Live2D entry in the host PetData JSON.
Never switches the sprite PetData current_pet or writes the sprite's stats.
"""
from __future__ import annotations

from copy import deepcopy
from tools.doro_role_progress import (
    ROLE_KEY, ACTIONS, _normalized, _owner, _MAX_COUNTER,
)

TASK_EVENTS = ("task_finished", "pomodoro_finished")
TASK_KEY = "doro_task_completions"
ACTION_EFFECTS = {
    "pat": (0, 1), "walk_left": (-1, 0),
    "walk_right": (-1, 0), "drop": (0, 0), "land": (0, 0),
}
TASK_EFFECTS = {"task_finished": (4, 3), "pomodoro_finished": (2, 1)}
TASK_COINS = {"task_finished": 5, "pomodoro_finished": 2}


def _prepared(pet_data):
    if not _owner(pet_data):
        return None
    profile = pet_data.allData_params.get(ROLE_KEY)
    if profile is None:
        return None
    result = _normalized(profile)
    if result is None:
        return None
    energy = result.get("HP")
    bond = result.get("FV")
    result["HP"] = (min(100, energy) if type(energy) is int and energy >= 0 else 80)
    result["FV"] = (min(100, bond) if type(bond) is int and bond >= 0 else 0)
    tasks = result.get(TASK_KEY)
    if not isinstance(tasks, dict):
        tasks = {}
    result[TASK_KEY] = {
        name: count if type(count) is int and 0 <= count <= _MAX_COUNTER else 0
        for name in TASK_EVENTS for count in [tasks.get(name, 0)]
    }
    return result


def _modify(record, effect):
    energy, bond = effect
    record["HP"] = min(100, max(0, record["HP"] + energy))
    record["FV"] = min(100, max(0, record["FV"] + bond))
    record["HP_tier"] = min(3, record["HP"] // 25)
    record["FV_lvl"] = min(5, record["FV"] // 20)


def _commit(pet_data, new_record):
    if pet_data.allData_params.get(ROLE_KEY) != new_record:
        pet_data.allData_params[ROLE_KEY] = new_record
        pet_data.save_data()


def ensure_doro_vitals(pet_data):
    """Migrate the old R63 HP=-1 sentinel only after model load."""
    record = _prepared(pet_data)
    if record is None:
        return None
    _modify(record, (0, 0))
    _commit(pet_data, record)
    return snapshot_doro_vitals(pet_data)


def record_doro_activity(pet_data, action):
    """Atomically count an actual action and update Doro's own state."""
    if action not in ACTIONS:
        return False
    record = _prepared(pet_data)
    if record is None:
        return False
    value = record["doro_interactions"][action]
    if value >= _MAX_COUNTER:
        return False
    record["doro_interactions"][action] = value + 1
    _modify(record, ACTION_EFFECTS[action])
    _commit(pet_data, record)
    return True


def record_doro_task(pet_data, event):
    """Reward only host-emitted finished tasks; cancelled tasks do not emit."""
    if event not in TASK_EVENTS:
        return False
    record = _prepared(pet_data)
    if record is None:
        return False
    value = record[TASK_KEY][event]
    if value >= _MAX_COUNTER:
        return False
    coins = record.get("coins")
    if type(coins) is not int or not 0 <= coins <= _MAX_COUNTER:
        return False
    if coins > _MAX_COUNTER - TASK_COINS[event]:
        return False
    record[TASK_KEY][event] = value + 1
    record["coins"] = coins + TASK_COINS[event]
    _modify(record, TASK_EFFECTS[event])
    _commit(pet_data, record)
    return True


def snapshot_doro_vitals(pet_data):
    """Isolated snapshot for the role UI, never an alias to writable saves."""
    record = _prepared(pet_data)
    if record is None:
        return None
    return {
        "energy": record["HP"],
        "bond": record["FV"],
        "coins": record.get("coins", 0),
        "tasks": deepcopy(record[TASK_KEY]),
    }

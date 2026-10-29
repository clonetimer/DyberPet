"""Doro-only purchasing and feeding using the EXISTING DyberPet item catalogue.

No invented food assets or parallel data file. The existing PetData's
"Doro Live2D" record owns its coins/items; other sprite roles are untouched.
All accepted mutations commit once via the original PetData.save_data().
"""
from __future__ import annotations

from copy import deepcopy

from tools.doro_role_progress import ROLE_KEY, _MAX_COUNTER
from tools.doro_vitals import _prepared, _modify, _commit

MAX_ITEM_COUNT = 9999
MAX_CATALOG_ITEMS = 8


def _valid_food(items_data, name):
    catalog = getattr(items_data, "item_dict", None)
    if not isinstance(catalog, dict) or not isinstance(name, str):
        return None
    product = catalog.get(name)
    if not isinstance(product, dict) or product.get("item_type") != "consumable":
        return None
    hp = product.get("effect_HP")
    fv = product.get("effect_FV")
    cost = product.get("cost")
    if any(type(value) is not int for value in (hp, fv, cost)):
        return None
    if not (0 <= cost <= _MAX_COUNTER and -100 <= hp <= 100 and -100 <= fv <= 100):
        return None
    # Feeding items must have an effect; do not accept empty/unrelated items.
    if hp == 0 and fv == 0:
        return None
    return {"name": name, "cost": cost, "energy": hp, "bond": fv}


def source_food_catalog(items_data):
    """List genuine consumables in a bounded in-app menu, not test sprites."""
    catalog = getattr(items_data, "item_dict", None)
    if not isinstance(catalog, dict):
        return []
    result = []
    for name in sorted(catalog):
        food = _valid_food(items_data, name)
        if food is not None:
            result.append(food)
    return result


def _inventory(profile):
    original = profile.get("items")
    if not isinstance(original, dict):
        return None
    stock = {}
    for name, pair in original.items():
        if (isinstance(name, str)
                and isinstance(pair, (list, tuple)) and len(pair) == 2
                and type(pair[0]) is int and type(pair[1]) is int
                and pair[0] > 0 and 0 < pair[1] <= MAX_ITEM_COUNT):
            stock[name] = [pair[0], pair[1]]
        else:
            # Do not silently overwrite a malformed legacy inventory.
            return None
    return stock


def doro_inventory(pet_data, items_data):
    """Readonly safe state; catalogue remains the host ItemData source."""
    profile = _prepared(pet_data)
    if profile is None:
        return None
    stock = _inventory(profile)
    coins = profile.get("coins")
    if stock is None or type(coins) is not int or not 0 <= coins <= _MAX_COUNTER:
        return None
    available = []
    for name, (_, count) in sorted(stock.items()):
        food = _valid_food(items_data, name)
        if food is not None:
            available.append({**food, "quantity": count})
    return {"coins": coins, "food": available}


def buy_doro_food(pet_data, items_data, name):
    """Spend Doro's own earned coins and add one genuine inventory item."""
    food = _valid_food(items_data, name)
    profile = _prepared(pet_data)
    if food is None or profile is None:
        return False
    stock = _inventory(profile)
    coins = profile.get("coins")
    if stock is None or type(coins) is not int or not 0 <= coins <= _MAX_COUNTER:
        return False
    if coins < food["cost"]:
        return False
    if name in stock:
        idx, count = stock[name]
        if count >= MAX_ITEM_COUNT:
            return False
        stock[name] = [idx, count + 1]
    else:
        next_idx = max([0, *(pair[0] for pair in stock.values())]) + 1
        stock[name] = [next_idx, 1]
    profile["coins"] = coins - food["cost"]
    profile["items"] = stock
    _commit(pet_data, profile)
    return True


def feed_doro(pet_data, items_data, name):
    """Consume one of Doro's food units, then update its own energy/bond."""
    food = _valid_food(items_data, name)
    profile = _prepared(pet_data)
    if food is None or profile is None:
        return False
    stock = _inventory(profile)
    if stock is None or name not in stock:
        return False
    idx, count = stock[name]
    if count == 1:
        stock.pop(name)
    else:
        stock[name] = [idx, count - 1]
    profile["items"] = stock
    _modify(profile, (food["energy"], food["bond"]))
    _commit(pet_data, profile)
    return True

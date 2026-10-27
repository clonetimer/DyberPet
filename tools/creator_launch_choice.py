"""R17: choose an actually installed creator role for the NEXT application start.

The currently running PetData/ActData is intentionally NOT hot-reloaded. Fresh
Genshin native inventory is authoritative; batch logs never prove identity,
art likeness, source rights or live desktop usability. No network or art writes.
"""
from __future__ import annotations


def verified_new_artist_folders(installation, inventory):
    """Return display-label -> actual folder, only if receipt AND fresh native
    inventory agree on the same source-bound person and non-demo folder.
    """
    if not isinstance(installation, dict) or not isinstance(inventory, dict):
        raise ValueError("Missing native creator installation inventory")
    results = installation.get("results")
    characters = inventory.get("characters")
    if not isinstance(results, list) or not isinstance(characters, list):
        raise ValueError("Invalid native creator results")
    recognized = set()
    for role in characters:
        if not isinstance(role, dict) or not isinstance(role.get("profile"), str):
            continue
        for item in role.get("installed_folders", []):
            if (isinstance(item, dict) and
                    item.get("is_original_demo") is False and
                    isinstance(item.get("folder"), str)):
                recognized.add((role["profile"], item["folder"]))
    options = {}
    for row in results:
        if (not isinstance(row, dict) or
                row.get("status") != "installed_unreviewed" or
                not isinstance(row.get("profile"), str)):
            continue
        folders = row.get("verified_native_folders")
        if not isinstance(folders, list):
            continue
        for folder in folders:
            if (not isinstance(folder, str) or not folder or
                    folder in (".", "..") or "/" in folder or
                    "\\" in folder or len(folder) > 120 or
                    (row["profile"], folder) not in recognized):
                continue
            options[f"{row['profile']} · {folder}"] = folder
    return options


def stage_default_pet(settings_module, folder, allowed_folders):
    """Persist restart-only choice, never dispatch change_pet on uninitialized art.

    Save errors restore the in-memory setting. Callers must populate the
    allowlist exclusively from freshly verified native role folders.
    """
    if (not isinstance(folder, str) or not folder or
            folder not in allowed_folders):
        raise ValueError("Next-start pet is not in the approved local selection")
    original = settings_module.default_pet
    settings_module.default_pet = folder
    try:
        settings_module.save_settings()
    except Exception:
        settings_module.default_pet = original
        raise
    return folder

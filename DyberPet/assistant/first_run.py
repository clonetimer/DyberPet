"""Side-effect-free, local-only first-launch detection and usable role discovery."""
from __future__ import annotations

import json
from pathlib import Path


SMOKE_FLAGS = frozenset(("--assistant-smoke", "--linux-ui-smoke", "--linux-bundle-diag"))


def needs_first_run(config_dir, argv=()):
    """Existing installs are never forced through the welcome dialog."""
    if any(flag in argv for flag in SMOKE_FLAGS):
        return False
    return not (Path(config_dir) / "data" / "settings.json").exists()


def installed_playable_roles(root):
    """Only native roles with actual frame files are available for selection.

    Do not substitute uninstalled roster *templates* for installed assets.
    Never generate/download art or edit an installed role while scanning.
    """
    root = Path(root)
    if not root.is_dir():
        return []
    result = []
    for folder in root.iterdir():
        if not folder.is_dir() or folder.is_symlink() or folder.name == "sys":
            continue
        configs = (folder / "pet_conf.json", folder / "act_conf.json")
        action = folder / "action"
        if any(not p.is_file() or p.is_symlink() for p in configs):
            continue
        if not action.is_dir() or action.is_symlink():
            continue
        # A tiny bound prevents expensive enumeration of user-supplied folders.
        image = next((p for p in action.glob("*.png")
                      if p.is_file() and not p.is_symlink()), None)
        if image is None:
            continue
        marker = folder / "BUILTIN_CHIBI_DEMO.json"
        demo = marker.is_file() or (folder / "BUILTIN_MASCOT_DEMO.json").is_file()
        # First-party roster demos carry Chinese display names. Read only a
        # bounded local manifest; untrusted/invalid metadata uses the folder ID.
        display = folder.name
        for metadata in (marker, folder / "info" / "info.json"):
            try:
                if metadata.is_symlink() or not metadata.is_file() or metadata.stat().st_size > 16384:
                    continue
                value = json.loads(metadata.read_text(encoding="utf-8")).get("name")
                if isinstance(value, str) and 1 <= len(value.strip()) <= 80:
                    display = value.strip()
                    break
            except (OSError, UnicodeError, ValueError, AttributeError):
                continue
        result.append({
            "folder": folder.name,
            "display": display,
            "preview": str(image),
            "demo": bool(demo),
        })
    result.sort(key=lambda item: (item["folder"] != "Kitty",
                                  item["folder"].casefold(), item["folder"]))
    return result

"""Side-effect-free, local-only first-launch detection and usable role discovery."""
from __future__ import annotations

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
        demo = (folder / "BUILTIN_CHIBI_DEMO.json").is_file() or (
            folder / "BUILTIN_MASCOT_DEMO.json").is_file()
        result.append({
            "folder": folder.name,
            "preview": str(image),
            "demo": bool(demo),
        })
    result.sort(key=lambda item: (item["folder"] != "Kitty",
                                  item["folder"].casefold(), item["folder"]))
    return result

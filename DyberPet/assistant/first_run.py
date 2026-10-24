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
        # Creator downloads are installed into safe ASCII folder IDs such as
        # SourceGenshinNahida. Read the display name from the LOCAL receipt so
        # Chinese searches find 纳西妲 rather than showing only an internal ID.
        display = folder.name
        artist_source = False
        for metadata in (folder / "PERSONAL_IMPORT.json", marker,
                         folder / "info" / "info.json"):
            try:
                if (metadata.is_symlink() or not metadata.is_file() or
                        metadata.stat().st_size > 16384):
                    continue
                record = json.loads(metadata.read_text(encoding="utf-8"))
                if not isinstance(record, dict):
                    continue
                value = record.get("display_name") or record.get("name")
                if isinstance(value, str) and 1 <= len(value.strip()) <= 80:
                    display = value.strip()
                if (metadata.name == "PERSONAL_IMPORT.json" and
                        record.get("source_kind") in
                        ("artist_original_animation", "curated_creator_spritesheet") and
                        isinstance(record.get("source_repository"), str)):
                    artist_source = True
                if display != folder.name:
                    break
            except (OSError, UnicodeError, ValueError, AttributeError):
                continue
        result.append({
            "folder": folder.name,
            "display": display,
            "preview": str(image),
            "demo": bool(demo),
            "artist_source": artist_source,
        })
    result.sort(key=lambda item: (item["folder"] != "Kitty",
                                  not item["artist_source"],
                                  item["folder"].casefold(), item["folder"]))
    return result

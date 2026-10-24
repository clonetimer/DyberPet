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


def _native_idle_preview(folder, action):
    """Prefer the actual configured idle frame, not an unrelated effect PNG.

    Artist packs may contain hundreds of skill/accessory images. Picking the
    first arbitrary frame can misleadingly show an effect instead of the pet.
    """
    try:
        pet_path = folder / "pet_conf.json"
        act_path = folder / "act_conf.json"
        if (any(path.is_symlink() or path.stat().st_size > 256 * 1024
                for path in (pet_path, act_path))):
            raise ValueError("Unsafe preview configuration")
        pet = json.loads(pet_path.read_text(encoding="utf-8"))
        actions = json.loads(act_path.read_text(encoding="utf-8"))
        default = actions.get(pet.get("default"), {})
        prefix = default.get("images") if isinstance(default, dict) else None
        if isinstance(prefix, str) and 1 <= len(prefix) <= 80 and "/" not in prefix and chr(92) not in prefix:
            for candidate in sorted(action.glob(prefix + "_*.png")):
                if candidate.is_file() and not candidate.is_symlink():
                    return candidate
    except (OSError, ValueError, TypeError, AttributeError, UnicodeError):
        pass
    # Legacy packs without a configured idle preview remain usable.
    return next((p for p in sorted(action.glob("*.png"))
                 if p.is_file() and not p.is_symlink()), None)


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
        # Use the configured character idle image for representative preview.
        image = _native_idle_preview(folder, action)
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

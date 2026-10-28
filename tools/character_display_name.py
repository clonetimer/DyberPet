"""Chinese character display names; never mutate stable folder/save identifiers."""
from __future__ import annotations

import json
from pathlib import Path
import re

ALIASES = {
    "kitty": "小猫",
    "chriskitty": "克里斯猫",
    "sourcewhalepet": "鲸鱼娘",
    "whalepet": "鲸鱼娘",
    "guga": "咕嘎",
    "sourceguga": "咕嘎",
    "doro": "朵萝",
    "sourcedoro": "朵萝",
    "sourcedorohanddrawnv2": "朵萝",
}
CHINESE = re.compile(r"[\u3400-\u9fff]")
MAX_JSON = 16 * 1024


def _read_local_json(path: Path) -> dict:
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_JSON:
            return {}
        obj = json.loads(path.read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else {}
    except (OSError, UnicodeError, ValueError):
        return {}


def chinese_character_name(folder_name: str, role_root: Path) -> str:
    """Show a grounded Chinese name and retain original ID for launch/save.

    Unknown third-party roles are not rebranded with a made-up translation;
    their provided name remains visible until user adds display_name_zh.
    """
    if not isinstance(folder_name, str) or not folder_name:
        return ""
    normalized = re.sub(r"_(\d+)$", "", folder_name).casefold()
    if normalized in ALIASES:
        return ALIASES[normalized]
    root = Path(role_root) / folder_name
    info = _read_local_json(root / "info" / "info.json")
    receipt = _read_local_json(root / "PERSONAL_IMPORT.json")
    for obj in (info, receipt):
        name = obj.get("display_name_zh")
        if isinstance(name, str) and CHINESE.search(name) and len(name) <= 80:
            return name.strip()
    profile = next((receipt.get(key) for key in ("selected_profile", "profile")
                    if isinstance(receipt.get(key), str)), None)
    if profile:
        try:
            from tools.chibi_profiles import CHIBI_PROFILES
            profile_row = CHIBI_PROFILES.get(profile, {})
            translated = profile_row.get("name")
            if isinstance(translated, str) and CHINESE.search(translated):
                return translated
        except ImportError:
            pass
    for name in (info.get("petName"), receipt.get("display_name")):
        if isinstance(name, str) and CHINESE.search(name) and len(name) <= 80:
            # Strip an appended English alias, but preserve Chinese qualifiers.
            return re.split(r"\s+(?=[A-Za-z][A-Za-z0-9 _-]*$)", name.strip())[0]
    # Folder may be an already-Chinese original name; keep it verbatim.
    return folder_name

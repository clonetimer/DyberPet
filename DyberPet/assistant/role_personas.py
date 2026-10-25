"""Resolve a role's nonofficial persona using explicit local binding receipts.

Do not guess the role identity from a folder name or from untrusted art.
Never alter files or accept linked role directories.
"""
from __future__ import annotations

from pathlib import Path

from .persona import PERSONAS


def persona_for_local_role(role_name, role_root):
    if (not isinstance(role_name, str) or not role_name or
            len(role_name) > 120 or role_name in (".", "..") or
            any(c in role_name for c in ("/", "\\", "\x00"))):
        return None
    if role_name in PERSONAS and role_name.startswith("genshin_"):
        return role_name
    root = Path(role_root).expanduser()
    if root.is_symlink() or not root.is_dir():
        return None
    folder = root / role_name
    if folder.is_symlink() or not folder.is_dir():
        return None
    try:
        from tools.genshin_library import _profile_of
        key = _profile_of(folder)
        return key if key in PERSONAS and key.startswith("genshin_") else None
    except (OSError, ValueError, TypeError, UnicodeError):
        return None

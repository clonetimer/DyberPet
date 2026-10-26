#!/usr/bin/env python3
"""Create a truly offline personal DyberPet portable copy on THIS PC only.

Only the user's currently installed local role files are embedded. No asset is
downloaded, committed, uploaded, or added to a hosted Release by this module.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import stat
import zipfile

from .genshin_library import scan_genshin_library
from .mascot_library import scan_mascot_library

# No private saves, voice paths, credentials, runtime caches or logs in the pack.
_EXCLUDE_ROOT_DIRS = {"data", "build", "wheelhouse", ".git",
                      ".venv", ".venv-personal65", "__pycache__"}
_EXCLUDE_NAMES = {"thumbs.db", ".ds_store"}
_MAX_TOTAL_INPUT = 8 * 1024**3
_MAX_FILE = 1024**3


def _checked_root(root):
    p = Path(root).expanduser()
    if p.is_symlink() or not p.is_dir():
        raise ValueError("Portable directory must be a real, existing directory")
    p = p.resolve()
    if not (p / "DyberPet.exe").is_file():
        raise ValueError("DyberPet.exe missing; select extracted Windows portable directory")
    role = p / "res" / "role"
    if role.is_symlink() or not role.is_dir():
        raise ValueError("Portable role directory is missing or linked")
    return p, role


def _entry_files(root):
    total = 0
    entries = []
    for base, dirs, files in os.walk(root, topdown=True, followlinks=False):
        folder = Path(base)
        relative = folder.relative_to(root)
        kept = []
        for name in sorted(dirs):
            current = folder / name
            if current.is_symlink():
                raise ValueError("Refusing linked directory in local pack: " + name)
            if (relative == Path(".") and name.casefold() in _EXCLUDE_ROOT_DIRS) or name == "__pycache__":
                continue
            kept.append(name)
        dirs[:] = kept
        for name in sorted(files):
            file = folder / name
            if file.is_symlink() or not file.is_file():
                raise ValueError("Refusing linked/unusual file: " + name)
            if name.casefold() in _EXCLUDE_NAMES or name.endswith((".pyc", ".tmp")):
                continue
            info = file.stat()
            if not stat.S_ISREG(info.st_mode):
                raise ValueError("Not a regular file: " + name)
            if info.st_size > _MAX_FILE:
                raise ValueError("Oversized entry: " + name)
            total += info.st_size
            if total > _MAX_TOTAL_INPUT:
                raise ValueError("Personal package exceeds local 8 GiB limit")
            entries.append((file, file.relative_to(root).as_posix()))
    return entries


def inspect_local_bundle(portable_root):
    root, role = _checked_root(portable_root)
    genshin = scan_genshin_library(role)
    mascot = scan_mascot_library(role)
    real_count = genshin["summary"]["personal_art_profile_count"]
    mascot_count = mascot["summary"]["imported_creator_art_count"]
    return {
        "format": "dyberpet-local-personal-zip-v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "contains_user_imported_art": real_count > 0 or mascot_count > 0,
        "genshin_installed_distinct_profiles": real_count,
        "genshin_65_source_target_reached": real_count >= 65,
        "mascot_creator_art_installed": mascot_count,
        "mascot_two_source_target_reached": mascot_count == 2,
        "unmapped_genshin_folders": genshin["summary"]["unmapped_folder_count"],
        "invalid_genshin_folders": genshin["summary"]["invalid_folder_count"],
        "invalid_mascot_folders": mascot["summary"]["invalid_count"],
        "author_rights_verified_by_tool": False,
        "game_likeness_verified_by_tool": False,
        "voice_fidelity_verified_by_tool": False,
        "real_windows_desktop_qa_verified": False,
        "only_local_generated_no_upload": True,
        "personal_data_dir_excluded": True,
    }


def create_local_bundle(portable_root, output, *, confirmed=False):
    """Produce a complete self-contained Windows app zip, with installed art.

    Confirmation must come from a local user action; never call in hosted CI
    with external third-party imagery or upload the result to any provider.
    """
    if not confirmed:
        raise ValueError("Explicit personal local bundle confirmation is required")
    root, _ = _checked_root(portable_root)
    output = Path(output).expanduser().absolute()
    if output.suffix.lower() != ".zip":
        raise ValueError("Local bundle output must be a .zip file")
    if output == root or root in output.parents:
        raise ValueError("Bundle must be outside the portable application directory")
    if output.is_symlink() or output.exists():
        raise FileExistsError("Bundle destination exists; never overwrite private role packages")
    if not output.parent.is_dir():
        raise ValueError("Bundle destination parent directory does not exist")
    manifest = inspect_local_bundle(root)
    entries = _entry_files(root)
    temporary = output.with_name(output.name + ".partial")
    if temporary.exists() or temporary.is_symlink():
        raise FileExistsError("Temporary bundle destination already exists")
    try:
        with zipfile.ZipFile(temporary, mode="x", compression=zipfile.ZIP_DEFLATED,
                             compresslevel=6, allowZip64=True) as archive:
            for file, name in entries:
                archive.write(file, arcname=name)
            archive.writestr("LOCAL_OFFLINE_BUILD.json",
                             json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
        os.replace(temporary, output)
    finally:
        if temporary.exists():
            temporary.unlink()
    digest = hashlib.sha256()
    with output.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    return {
        "local_archive": str(output),
        "size_bytes": output.stat().st_size,
        "sha256": digest.hexdigest(),
        "file_count": len(entries) + 1,
        "manifest": manifest,
    }

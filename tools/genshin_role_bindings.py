#!/usr/bin/env python3
"""Explicit, non-destructive local character associations for legacy MODs.

Mappings live beside other user data; they never change an installed MOD,
fabricate likeness/rights, download files, or act as a release approval.
Each record is anchored to a digest of the exact native role configuration.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path

try:
    from .chibi_profiles import CHIBI_PROFILES, match_chibi_profile
    from .install_native_role import inspect_native_folder
except ImportError:
    from chibi_profiles import CHIBI_PROFILES, match_chibi_profile
    from install_native_role import inspect_native_folder

MAX_MAPPING_SIZE = 256 * 1024
MAX_MAPPINGS = 3000
_SHA = re.compile(r"[a-f0-9]{64}")


def default_mapping_path(role_root):
    root = Path(role_root).expanduser()
    if root.is_symlink():
        raise ValueError("Linked role root is not supported")
    # This works for a portable tree: <root>/res/role -> <root>/data.
    # A custom role directory should pass --mappings explicitly.
    return root.parent.parent / "data" / "genshin_role_bindings.json"


def _validate_folder_name(folder):
    if not isinstance(folder, str) or not folder or folder in (".", ".."):
        raise ValueError("Choose an existing single role folder name")
    if "/" in folder or "\\" in folder or "\x00" in folder:
        raise ValueError("Role folder must be a single local directory")
    return folder


def _checked_paths(role_root, mappings):
    role_root = Path(role_root).expanduser()
    mappings = Path(mappings).expanduser()
    if role_root.is_symlink():
        raise ValueError("Role root cannot be a symlink")
    if mappings.is_symlink() or mappings.parent.is_symlink():
        raise ValueError("Mapping file or parent cannot be a symlink")
    if mappings.exists() and not mappings.is_file():
        raise ValueError("Mapping location must be a file")
    return role_root, mappings


def config_digest(folder):
    """Bind two native configs, not guessed role names or full GB-size frames."""
    f = Path(folder)
    h = hashlib.sha256()
    for name in ("pet_conf.json", "act_conf.json"):
        p = f / name
        if not p.is_file() or p.is_symlink():
            raise ValueError("Role configuration missing or linked: " + name)
        if p.stat().st_size > 1024 * 1024:
            raise ValueError("Character configuration exceeds 1 MiB")
        raw = p.read_bytes()
        h.update(name.encode("ascii") + b"\x00")
        h.update(str(len(raw)).encode("ascii") + b"\x00")
        h.update(raw)
    return h.hexdigest()


def load_bindings(role_root, mappings=None):
    """No writes. Reject unsafe/broken manifests rather than silently ignoring."""
    role_root = Path(role_root).expanduser()
    mappings = mappings or default_mapping_path(role_root)
    _, path = _checked_paths(role_root, mappings)
    if not path.exists():
        return {}
    if path.stat().st_size > MAX_MAPPING_SIZE:
        raise ValueError("Mapping catalogue exceeds safe limits")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("schema") != 1:
        raise ValueError("Unsupported role-association schema")
    rows = raw.get("roles")
    if not isinstance(rows, dict) or len(rows) > MAX_MAPPINGS:
        raise ValueError("Invalid number of role associations")
    for folder, record in rows.items():
        _validate_folder_name(folder)
        if (not isinstance(record, dict)
                or record.get("profile") not in CHIBI_PROFILES
                or not str(record.get("profile")).startswith("genshin_")
                or not isinstance(record.get("config_sha256"), str)
                or not _SHA.fullmatch(record["config_sha256"])):
            raise ValueError("Invalid role association entry: " + folder)
    return rows


def binding_status(role_folder, mapping):
    """A changed original MOD must never be silently considered associated."""
    if not mapping:
        return None
    folder = Path(role_folder)
    if folder.is_symlink() or not folder.is_dir():
        return None
    try:
        return mapping["profile"] if config_digest(folder) == mapping["config_sha256"] else None
    except (ValueError, OSError):
        return None


def _store_bindings(role_root, mapping_file, rows):
    role_root, target = _checked_paths(role_root, mapping_file)
    if len(rows) > MAX_MAPPINGS:
        raise ValueError("Too many local role associations")
    encoded = (json.dumps({"schema": 1, "roles": rows}, ensure_ascii=False,
                          sort_keys=True, indent=2) + "\n").encode("utf-8")
    if len(encoded) > MAX_MAPPING_SIZE:
        raise ValueError("Local role-association file exceeds safe size")
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.parent.is_symlink() or target.is_symlink():
        raise ValueError("Linked association location is not writable")
    name = None
    try:
        fd, name = tempfile.mkstemp(dir=target.parent, prefix=".genshin-bind-", suffix=".json")
        with os.fdopen(fd, "wb") as output:
            output.write(encoded)
            output.flush()
            os.fsync(output.fileno())
        if target.is_symlink():
            raise ValueError("Association file became linked")
        os.replace(name, target)
    finally:
        if name and os.path.exists(name):
            os.unlink(name)


def associate_existing_role(role_root, folder, profile, *,
                            mappings=None, confirmed=False):
    """Explicitly bind a legacy single role with no source receipt."""
    if not confirmed:
        raise ValueError("Explicit user confirmation required to associate local art")
    folder = _validate_folder_name(folder)
    if profile not in CHIBI_PROFILES or not profile.startswith("genshin_"):
        raise ValueError("Choose an existing Genshin character template")
    role_root = Path(role_root).expanduser()
    mapping_file = mappings or default_mapping_path(role_root)
    _checked_paths(role_root, mapping_file)
    role = role_root / folder
    if role.is_symlink():
        raise ValueError("Refusing linked character folder")
    inspect_native_folder(role)
    # A deliberately chosen import receipt is authoritative; don't override.
    try:
        from .genshin_library import _profile_of
    except ImportError:
        from genshin_library import _profile_of
    source_profile = _profile_of(role)
    if source_profile is not None:
        raise ValueError("Role already has an explicit import profile; do not override")
    rows = dict(load_bindings(role_root, mapping_file))
    if folder in rows:
        raise ValueError("Role has a local association; remove it explicitly before changing")
    digest = config_digest(role)
    rows[folder] = {"profile": profile, "config_sha256": digest}
    _store_bindings(role_root, mapping_file, rows)
    return {"folder": folder, "profile": profile, "config_sha256": digest,
            "scope": "local_only", "identity_verified": False,
            "desktop_qa_verified": False, "rights_verified": False}


def unbind_existing_role(role_root, folder, *, mappings=None, confirmed=False):
    """Remove sidecar only; never delete or alter source character files."""
    if not confirmed:
        raise ValueError("Explicit user confirmation required to unlink local role")
    folder = _validate_folder_name(folder)
    mapping_file = mappings or default_mapping_path(role_root)
    rows = dict(load_bindings(role_root, mapping_file))
    if folder not in rows:
        raise ValueError("No sidecar association for this role")
    rows.pop(folder)
    _store_bindings(role_root, mapping_file, rows)
    return {"folder": folder, "association_removed": True,
            "original_role_modified": False}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--role-root", type=Path,
                    default=Path(__file__).resolve().parents[1] / "res" / "role")
    ap.add_argument("--mappings", type=Path)
    commands = ap.add_subparsers(dest="command", required=True)
    link = commands.add_parser("link", help="Associate an existing local MOD with a template")
    link.add_argument("--folder", required=True)
    link.add_argument("--character", required=True, help="Chinese, English or stable profile ID")
    link.add_argument("--confirm-local", action="store_true")
    unlink = commands.add_parser("unlink", help="Remove only a local association record")
    unlink.add_argument("--folder", required=True)
    unlink.add_argument("--confirm-local", action="store_true")
    args = ap.parse_args(argv)
    try:
        if args.command == "link":
            result = associate_existing_role(
                args.role_root, args.folder, match_chibi_profile(args.character),
                mappings=args.mappings, confirmed=args.confirm_local)
        else:
            result = unbind_existing_role(
                args.role_root, args.folder,
                mappings=args.mappings, confirmed=args.confirm_local)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        ap.exit(1, "Local role association blocked: " + str(exc) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())

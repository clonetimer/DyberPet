#!/usr/bin/env python3
"""Read-only local role inventory. Templates are not installed characters.

Only explicit local-import receipts can associate user-provided artwork with
a Genshin template. Never infer authorship/identity from filenames, and never
claim true desktop playability from a static JSON/PNG check.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from .chibi_profiles import CHIBI_PROFILES
    from .install_native_role import inspect_native_folder
except ImportError:
    from chibi_profiles import CHIBI_PROFILES
    from install_native_role import inspect_native_folder

_MAX_RECEIPT_BYTES = 128 * 1024


def _read_receipt(path):
    if not path.is_file() or path.is_symlink():
        return None
    if path.stat().st_size > _MAX_RECEIPT_BYTES:
        raise ValueError("Receipt too large")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Receipt must be an object")
    return data


def _profile_of(folder):
    """Prefer an explicit PERSONAL_IMPORT binding; detect contradictory IDs."""
    found = []
    for name, field in (("PERSONAL_IMPORT.json", "selected_profile"),
                        ("IMPORT_REPORT.json", "profile")):
        receipt = _read_receipt(folder / name)
        if receipt is not None:
            val = receipt.get(field)
            if val is not None:
                if not isinstance(val, str):
                    raise ValueError("Invalid profile in local receipt")
                found.append(val)
    if len(set(found)) > 1:
        raise ValueError("Conflicting character profiles in local receipts")
    return found[0] if found else None


def scan_genshin_library(role_root):
    """Return a detached, JSON-safe catalogue; no writes or absolute paths."""
    catalog = {key: CHIBI_PROFILES[key]["name"]
               for key in sorted(CHIBI_PROFILES)
               if key.startswith("genshin_")}
    root = Path(role_root).expanduser()
    if root.is_symlink():
        raise ValueError("Refusing linked role root")
    if root.exists() and not root.is_dir():
        raise ValueError("Role root must be a directory")
    result = {key: {"profile": key, "name": name, "status": "template_only",
                    "installed_folders": [], "desktop_qa_verified": False,
                    "rights_verified": False}
              for key, name in catalog.items()}
    unmapped, invalid, total = [], [], 0
    if root.exists():
        for folder in sorted(root.iterdir(), key=lambda p: p.name.casefold()):
            if folder.name.startswith("."):
                continue
            if folder.is_symlink():
                invalid.append({"folder": folder.name, "reason": "linked_entry"})
                continue
            if not folder.is_dir():
                continue
            total += 1
            try:
                profile = _profile_of(folder)
                # Native folder preflight rejects linked children and unsafe
                # contents as well as invalid animation references.
                report = inspect_native_folder(folder)
                if profile not in catalog:
                    unmapped.append({"folder": folder.name, "status": "unmapped_local",
                                     "actions": report["validation"]["actions"]})
                    continue
                entry = result[profile]
                entry["installed_folders"].append({
                    "folder": folder.name,
                    "actions": report["validation"]["actions"],
                    "frames": report["validation"]["images"],
                })
                entry["status"] = "structurally_installed"
            except (ValueError, OSError, UnicodeError, TypeError,
                    json.JSONDecodeError) as exc:
                invalid.append({"folder": folder.name, "reason": "invalid_local_role",
                                "message": str(exc)[:200]})
    return {
        "scope": "local_read_only",
        "note": "Structure checked only; actual Windows animation, likeness and art rights not verified",
        "summary": {
            "template_count": len(catalog),
            "installed_profile_count": sum(
                bool(v["installed_folders"]) for v in result.values()),
            "pending_template_count": sum(
                not v["installed_folders"] for v in result.values()),
            "local_folder_count": total,
            "unmapped_folder_count": len(unmapped),
            "invalid_folder_count": len(invalid),
        },
        "characters": list(result.values()),
        "unmapped_local": unmapped,
        "invalid_local": invalid,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--role-root", type=Path,
                    default=Path(__file__).resolve().parents[1] / "res" / "role")
    ap.add_argument("--only", choices=("all", "installed", "pending"), default="all")
    args = ap.parse_args(argv)
    try:
        result = scan_genshin_library(args.role_root)
        if args.only != "all":
            wanted = ("structurally_installed" if args.only == "installed"
                      else "template_only")
            result["characters"] = [
                x for x in result["characters"] if x["status"] == wanted]
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError) as exc:
        ap.exit(1, "Library inspection blocked: " + str(exc) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())

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
    from .genshin_role_bindings import load_bindings, binding_status
except ImportError:
    from chibi_profiles import CHIBI_PROFILES
    from install_native_role import inspect_native_folder
    from genshin_role_bindings import load_bindings, binding_status

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




def _demo_profile(folder):
    """Only a first-party mathematical sprite receipt counts as a demo."""
    record = _read_receipt(folder / "BUILTIN_CHIBI_DEMO.json")
    if record is None:
        return None
    if (record.get("generator") != "DyberPet-first-party-abstract-chibi-v1"
            or record.get("official_character_art") is not False
            or record.get("original_illustration") is not True):
        raise ValueError("Invalid or contradictory built-in demo receipt")
    value = record.get("profile")
    if not isinstance(value, str) or not value.startswith("genshin_"):
        raise ValueError("Invalid built-in demo profile")
    return value

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
    demo = _demo_profile(folder)
    if demo is not None:
        found.append(demo)
    if len(set(found)) > 1:
        raise ValueError("Conflicting character profiles in local receipts")
    return found[0] if found else None


def scan_genshin_library(role_root, mappings=None):
    """Return a detached, JSON-safe catalogue; no writes or absolute paths."""
    catalog = {key: CHIBI_PROFILES[key]["name"]
               for key in sorted(CHIBI_PROFILES)
               if key.startswith("genshin_")}
    root = Path(role_root).expanduser()
    if root.is_symlink():
        raise ValueError("Refusing linked role root")
    if root.exists() and not root.is_dir():
        raise ValueError("Role root must be a directory")
    bindings = load_bindings(root, mappings)
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
                binding = bindings.get(folder.name)
                if binding and profile and profile != binding["profile"]:
                    raise ValueError("Conflicting local and original import identities")
                stale = bool(binding and not profile and not binding_status(folder, binding))
                if binding and not profile and not stale:
                    profile = binding["profile"]
                # Native folder preflight rejects linked children and unsafe
                # contents as well as invalid animation references.
                report = inspect_native_folder(folder)
                if profile not in catalog:
                    unmapped.append({"folder": folder.name,
                                     "status": "stale_association" if stale else "unmapped_local",
                                     "actions": report["validation"]["actions"]})
                    continue
                entry = result[profile]
                is_demo = _demo_profile(folder) is not None
                entry["installed_folders"].append({
                    "is_original_demo": is_demo,
                    "folder": folder.name,
                    "actions": report["validation"]["actions"],
                    "frames": report["validation"]["images"],
                })
                if not is_demo:
                    entry["status"] = "structurally_installed"
                elif entry["status"] == "template_only":
                    entry["status"] = "demo_installed"
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
            "original_demo_profile_count": sum(
                any(x.get("is_original_demo") for x in v["installed_folders"])
                for v in result.values()),
            "personal_art_profile_count": sum(
                any(not x.get("is_original_demo") for x in v["installed_folders"])
                for v in result.values()),
            "pending_template_count": sum(
                not v["installed_folders"] for v in result.values()),
            "local_folder_count": total,
            "unmapped_folder_count": len(unmapped),
            "stale_association_count": sum(
                x["status"] == "stale_association" for x in unmapped),
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
    ap.add_argument("--mappings", type=Path, help="Optional local sidecar associations")
    args = ap.parse_args(argv)
    try:
        result = scan_genshin_library(args.role_root, args.mappings)
        if args.only != "all":
            selected = (("structurally_installed", "demo_installed")
                        if args.only == "installed" else ("template_only",))
            result["characters"] = [
                x for x in result["characters"] if x["status"] in selected]
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError) as exc:
        ap.exit(1, "Library inspection blocked: " + str(exc) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())

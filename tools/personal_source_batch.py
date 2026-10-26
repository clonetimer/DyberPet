#!/usr/bin/env python3
"""Plan or explicitly install pinned creator art on one local PC.

No artwork is bundled, uploaded to GitHub or placed into a public Release.
A pinned source is not an artist-rights, game-likeness or playback approval.
"""
from __future__ import annotations

import argparse
import importlib
import json
from pathlib import Path
import sys

try:
    from .character_source_coverage import source_coverage
    from .genshin_library import scan_genshin_library
except ImportError:
    from character_source_coverage import source_coverage
    from genshin_library import scan_genshin_library

# React LFS entries require a user-provided source file, and remain manual-only.
def default_role_root():
    """PyInstaller helper installs beside DyberPet.exe, never in _MEIPASS."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "res" / "role"
    return Path(__file__).resolve().parents[1] / "res" / "role"


INSTALLERS = {
    "native": ("tools.install_artist_genshin", "install_artist_genshin"),
    "codex": ("tools.install_artist_codex", "install_artist_codex"),
    "shimeji": ("tools.install_artist_shimeji", "install_artist_shimeji"),
    "nano_shimeji": ("tools.install_nanopet_shimeji", "install_nanopet_shimeji"),
    "independent_codex": ("tools.install_external_codex", "install_external_codex"),
    "codexpetdb_zip": ("tools.install_pinned_codexpetdb", "install_pinned_codexpetdb"),
}


def plan_personal_sources(role_root, *, only_profiles=None,
                          coverage=None, inventory=None):
    """Read-only plan; never download or create a character directory."""
    root = Path(role_root).expanduser()
    if root.is_symlink() or (root.exists() and not root.is_dir()):
        raise ValueError("Role root must be a real directory, not a symlink")
    coverage = source_coverage() if coverage is None else coverage
    inventory = scan_genshin_library(root) if inventory is None else inventory
    installed = {
        item["profile"] for item in inventory["characters"]
        if any(not f.get("is_original_demo", False)
               for f in item.get("installed_folders", []))
    }
    entries = coverage["characters"]
    known = {r["id"] for r in entries}
    selected = set(only_profiles) if only_profiles is not None else known
    if not selected.issubset(known):
        raise ValueError("Unknown role profile(s): " + ", ".join(sorted(selected - known)))
    planned = []
    for role in entries:
        profile = role["id"]
        if profile not in selected:
            continue
        options = role["source_candidates"]  # Existing source preference ordering.
        supported = next((o for o in options if o["provider"] in INSTALLERS), None)
        chosen = supported or (options[0] if options else None)
        status = ("already_installed" if profile in installed else
                  "missing_source" if chosen is None else
                  "manual_import_only" if chosen["provider"] not in INSTALLERS else
                  "ready_for_opt_in")
        planned.append({
            "profile": profile, "name": role["name"], "status": status,
            "source_count": len(options),
            "provider": chosen["provider"] if chosen else None,
            "source_key": chosen["source_key"] if chosen else None,
            "source_url": chosen["url"] if chosen else None,
            "original_likeness_verified": False,
            "rights_verified_by_tool": False,
            "real_device_playback_verified": False,
        })
    return {
        "scope": "personal_local_install_plan_no_artwork_included",
        "summary": {
            "selected_profiles": len(planned),
            "already_installed_structurally": sum(x["status"] == "already_installed" for x in planned),
            "ready_for_opt_in": sum(x["status"] == "ready_for_opt_in" for x in planned),
            "manual_import_only": sum(x["status"] == "manual_import_only" for x in planned),
            "missing_source": sum(x["status"] == "missing_source" for x in planned),
            "local_invalid_folders": len(inventory.get("invalid_local", [])),
        },
        "note": "PINNED SOURCE != INSTALLED/APPROVED ART. Rights, likeness, voice and live playback remain unverified.",
        "characters": planned,
    }


def install_personal_plan(plan, role_root, *, confirmed=False, max_roles=None,
                          dispatch=None):
    """Install chosen sources locally, logging individual failures without overwrite."""
    if not confirmed:
        raise ValueError("Explicit --accept-personal-use confirmation required")
    root = Path(role_root).expanduser()
    if root.is_symlink() or (root.exists() and not root.is_dir()):
        raise ValueError("Role root must be a real directory, not a symlink")
    if max_roles is not None and (not isinstance(max_roles, int) or max_roles < 1):
        raise ValueError("max_roles must be a positive integer")
    if dispatch is None:
        def dispatch(provider, key, dest):
            module, name = INSTALLERS[provider]
            return getattr(importlib.import_module(module), name)(key, dest, confirmed=True)
    results = []
    count = 0
    for item in plan["characters"]:
        if item["status"] != "ready_for_opt_in":
            continue
        if max_roles is not None and count >= max_roles:
            break
        count += 1
        profile, provider, key = item["profile"], item["provider"], item["source_key"]
        if provider not in INSTALLERS:
            raise ValueError("Unrecognized installer in personal plan")
        try:
            dispatch(provider, key, root)
        except (OSError, ValueError, RuntimeError, KeyError, TypeError) as exc:
            results.append({"profile": profile, "status": "failed",
                            "reason": type(exc).__name__ + ": " + str(exc)[:240]})
        else:
            results.append({"profile": profile, "status": "installed_unreviewed",
                            "provider": provider, "source_key": key})
    return {
        "scope": "local_personal_install_only", "attempted": count,
        "installed_unreviewed": sum(x["status"] == "installed_unreviewed" for x in results),
        "failed": sum(x["status"] == "failed" for x in results),
        "results": results, "no_artwork_uploaded": True,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--role-root", type=Path,
                    default=default_role_root())
    ap.add_argument("--profile", action="append", default=None,
                    help="Repeatable genshin_... profile (default: all 123 templates)")
    ap.add_argument("--install", action="store_true",
                    help="Actually fetch selected exact-pinned sources to local role folder")
    ap.add_argument("--accept-personal-use", action="store_true",
                    help="Explicit opt-in; review each creator's use conditions yourself")
    ap.add_argument("--max-roles", type=int, default=None,
                    help="Maximum installation attempts (try two first)")
    ap.add_argument("--output", type=Path,
                    help="Optional .json plan/report path; never an art archive")
    args = ap.parse_args(argv)
    try:
        plan = plan_personal_sources(args.role_root, only_profiles=args.profile)
        if args.install:
            result = {"plan_summary": plan["summary"],
                      "installation": install_personal_plan(
                          plan, args.role_root, confirmed=args.accept_personal_use,
                          max_roles=args.max_roles)}
        else:
            if args.accept_personal_use:
                ap.error("--accept-personal-use requires --install")
            result = plan
        output = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            if args.output.suffix.lower() != ".json":
                raise ValueError("Report must use .json extension")
            args.output.write_text(output, encoding="utf-8")
        else:
            if hasattr(sys.stdout, "reconfigure"):
                sys.stdout.reconfigure(encoding="utf-8")
            print(output, end="")
        return 0 if not args.install or not result["installation"]["failed"] else 1
    except (OSError, ValueError, KeyError, TypeError) as exc:
        ap.exit(2, "Personal source plan blocked: " + str(exc) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())

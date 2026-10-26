"""Local-only Guga/Doro creator source planner and confirmed installer.

This never redistributes original art and never claims original likeness/voice.
"""
from __future__ import annotations

import json
from pathlib import Path

try:
    from .install_creator_mascots import UPSTREAM, REPO, PINNED_REVISION, install_creator_mascot
    from .mascot_library import scan_mascot_library
except ImportError:
    from tools.install_creator_mascots import UPSTREAM, REPO, PINNED_REVISION, install_creator_mascot
    from tools.mascot_library import scan_mascot_library


def plan_mascot_sources(role_root, *, inventory=None):
    root = Path(role_root).expanduser()
    if root.is_symlink() or (root.exists() and not root.is_dir()):
        raise ValueError("Mascot role root must be a real directory")
    inventory = scan_mascot_library(root) if inventory is None else inventory
    installed = {row["key"] for row in inventory["mascots"]
                 if row.get("imported_creator_art")}
    names = {row["key"]: row["display_name"] for row in inventory["mascots"]}
    roles = []
    for key in ("guga", "doro"):
        item = UPSTREAM[key]
        roles.append({
            "key": key,
            "name": names[key],
            "status": "already_installed" if key in installed else "ready_for_opt_in",
            "source": f"https://github.com/{REPO}/tree/{PINNED_REVISION}/pets/{item['id']}",
            "source_kind": "creator_fan_art",
            "original_likeness_verified": False,
            "original_voice_included": False,
            "rights_verified": False,
            "physical_desktop_qa_verified": False,
        })
    return {
        "scope": "local_only_guga_doro_creator_art",
        "summary": {
            "mascot_templates": 2,
            "installed_creator_profiles": len(installed & {"guga", "doro"}),
            "ready_for_opt_in": sum(r["status"] == "ready_for_opt_in" for r in roles),
            "invalid_local_folders": len(inventory.get("invalid_local", [])),
        },
        "mascots": roles,
        "note": "Creator fan-art source has no voice bundle or automatic game/creator likeness approval.",
    }


def install_mascot_plan(plan, role_root, *, confirmed=False, installer=None):
    if not confirmed:
        raise ValueError("Confirm creator-source conditions and local personal use")
    root = Path(role_root).expanduser()
    if root.is_symlink() or (root.exists() and not root.is_dir()):
        raise ValueError("Mascot role root must be a real directory")
    installer = installer or install_creator_mascot
    results = []
    for row in plan["mascots"]:
        if row["status"] != "ready_for_opt_in":
            continue
        try:
            result = installer(row["key"], root, confirmed=True)
            if not isinstance(result, dict) or result.get("kind") != row["key"]:
                raise ValueError("Mascot installer returned mismatched identity")
            results.append({"key": row["key"], "status": "installed_unreviewed",
                            "native_actions": result.get("actions"),
                            "native_frames": result.get("frames")})
        except (OSError, ValueError, RuntimeError, KeyError, TypeError) as exc:
            results.append({"key": row["key"], "status": "failed",
                            "reason": f"{type(exc).__name__}: {str(exc)[:200]}"})
    return {
        "scope": "local_only_mascot_install",
        "installed_unreviewed": sum(x["status"] == "installed_unreviewed" for x in results),
        "failed": sum(x["status"] == "failed" for x in results),
        "no_art_uploaded": True,
        "results": results,
    }

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


def install_mascot_plan(plan, role_root, *, confirmed=False, installer=None,
                        inventory_reader=None, progress=None):
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
        if progress is not None:
            progress({"stage": "role_start", "key": row["key"]})
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
    verify = scan_mascot_library if inventory_reader is None else inventory_reader
    verified = set()
    inventory_error = None
    try:
        current = verify(root)
        verified = {entry["key"] for entry in current["mascots"]
                    if entry.get("imported_creator_art")}
    except (OSError, ValueError, RuntimeError, KeyError, TypeError) as exc:
        inventory_error = type(exc).__name__ + ": " + str(exc)[:180]
    for result in results:
        if result["status"] == "installed_unreviewed":
            if result["key"] not in verified:
                result["status"] = "failed"
                result["post_install_validation_failed"] = True
                result["reason"] = ("Local inventory verification unavailable: " + inventory_error
                                    if inventory_error else
                                    "Mascot importer returned, but valid creator artwork is not "
                                    "registered for the requested mascot")
            else:
                result["post_install_validation_passed"] = True
        if progress is not None:
            progress({"stage": "role_verified", "key": result["key"],
                      "status": result["status"]})
    return {
        "scope": "local_only_mascot_install",
        "installed_unreviewed": sum(x["status"] == "installed_unreviewed" for x in results),
        "failed": sum(x["status"] == "failed" for x in results),
        "no_art_uploaded": True,
        "post_install_inventory_checked": inventory_error is None,
        "post_install_inventory_error": inventory_error,
        "post_install_recognized_mascots": len(verified),
        "results": results,
    }

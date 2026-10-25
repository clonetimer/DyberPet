#!/usr/bin/env python3
"""Read-only per-character original-art animation/interaction coverage ledger.

Demos are explicitly excluded. Neither structural frames nor action names
certify a character's art likeness or that an action is currently unlocked.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from DyberPet.assistant.role_interactions import available_interactions

MAX_ACTION_CONFIG_BYTES = 512 * 1024


def _original_art_action_names(root, folder):
    target = root / folder / "act_conf.json"
    if target.is_symlink() or not target.is_file() or target.stat().st_size > MAX_ACTION_CONFIG_BYTES:
        raise ValueError("Unsafe or missing action configuration")
    data = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Action map must be an object")
    return [name for name in data if isinstance(name, str)]


def interaction_coverage(role_root, *, genshin_snapshot=None, mascot_snapshot=None):
    root = Path(role_root).expanduser()
    if root.is_symlink():
        raise ValueError("Linked role directory refused")
    if genshin_snapshot is None:
        from tools.genshin_library import scan_genshin_library
        genshin = scan_genshin_library(root)
    else:
        genshin = genshin_snapshot
    if mascot_snapshot is None:
        from tools.mascot_library import scan_mascot_library
        mascots = scan_mascot_library(root)
    else:
        mascots = mascot_snapshot
    rows = []

    def record(profile, name, family, folders):
        actual_folders = [x["folder"] for x in folders]
        all_names = set()
        errors = []
        for folder in actual_folders:
            try:
                all_names.update(_original_art_action_names(root, folder))
            except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
                errors.append({"folder": folder, "reason": str(exc)[:160]})
        interactions = available_interactions(sorted(all_names))
        rows.append({
            "id": profile, "name": name, "family": family,
            "imported_creator_role_count": len(actual_folders),
            "original_creator_art_present": bool(actual_folders),
            "actual_action_names": sorted(all_names),
            "action_categories_present_in_art": [x["id"] for x in interactions if x["available"]],
            "action_categories_missing_in_art": [x["id"] for x in interactions if not x["available"]],
            "runtime_unlock_qa_verified": False,
            "character_likeness_qa_verified": False,
            "per_role_interaction_qa_verified": False,
            "errors": errors,
        })

    for item in genshin["characters"]:
        personal = [x for x in item["installed_folders"] if not x.get("is_original_demo")]
        record(item["profile"], item["name"], "genshin", personal)
    for item in mascots["mascots"]:
        record("mascot_" + item["key"], item["display_name"], "mascot",
               item["imported_creator_art"])

    return {
        "scope": "local_read_only_original_art_only",
        "summary": {
            "template_total": len(rows),
            "roles_with_creator_art": sum(r["original_creator_art_present"] for r in rows),
            "roles_with_at_least_one_interaction": sum(
                bool(r["action_categories_present_in_art"]) for r in rows),
            "roles_missing_all_original_art_interactions": sum(
                not r["action_categories_present_in_art"] for r in rows),
            "roles_with_read_errors": sum(bool(r["errors"]) for r in rows),
            "human_likeness_approved": 0,
            "full_runtime_interaction_qa_approved": 0,
        },
        "characters": rows,
        "note": ("Original/demo characters NEVER count as creator-art coverage. "
                 "This report is a static asset action inventory, NOT proof of runtime "
                 "unlock, actual Qt playback, original identity, voice, or rights."),
    }



def inspect_selected_role_interactions(role_root, role_name, *, unlocked_actions=()):
    """Inspect one active role without scanning all 125 character directories.

    A locally created receipt cannot prove official art provenance or likeness;
    imported and built-in demonstration assets are deliberately distinguished.
    """
    root = Path(role_root).expanduser()
    if root.is_symlink() or (root.exists() and not root.is_dir()):
        raise ValueError("Unsafe installed role root")
    if (not isinstance(role_name, str) or not role_name or
            len(role_name) > 120 or role_name in (".", "..") or
            "/" in role_name or chr(92) in role_name or chr(0) in role_name):
        raise ValueError("Invalid role folder name")
    folder = root / role_name
    if folder.is_symlink():
        raise ValueError("Linked role folder refused")
    if not folder.is_dir():
        return {
            "role": role_name, "status": "not_installed",
            "on_disk_action_names": [], "installed_action_categories": [],
            "currently_unlocked_categories": [], "missing_categories": [
                x["id"] for x in available_interactions([])],
            "art_likeness_qa_passed": False, "physical_desktop_qa_passed": False,
        }
    for receipt in ("PERSONAL_IMPORT.json", "IMPORT_REPORT.json",
                    "BUILTIN_CHIBI_DEMO.json", "BUILTIN_MASCOT_DEMO.json"):
        if (folder / receipt).is_symlink():
            raise ValueError("Linked role receipt refused")
    demo = ((folder / "BUILTIN_CHIBI_DEMO.json").is_file() or
            (folder / "BUILTIN_MASCOT_DEMO.json").is_file())
    imported = ((folder / "PERSONAL_IMPORT.json").is_file() or
                (folder / "IMPORT_REPORT.json").is_file())
    status = ("builtin_demo_not_original_art" if demo else
              "imported_artist_claim_not_verified" if imported else
              "unverified_local_role")
    action_names = _original_art_action_names(root, role_name)
    on_disk = available_interactions(action_names)
    now_unlocked = set(x for x in unlocked_actions if isinstance(x, str))
    live = available_interactions(
        [name for name in action_names if name in now_unlocked])
    return {
        "role": role_name,
        "status": status,
        "on_disk_action_names": sorted(action_names),
        "installed_action_categories": [x["id"] for x in on_disk if x["available"]],
        "currently_unlocked_categories": [x["id"] for x in live if x["available"]],
        "missing_categories": [x["id"] for x in on_disk if not x["available"]],
        "art_likeness_qa_passed": False,
        "physical_desktop_qa_passed": False,
        "note": ("These are installed action-name hints only; source art, "
                 "real playback, animation uniqueness and rights await visual review."),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--role-root", type=Path,
                    default=Path(__file__).resolve().parents[1] / "res" / "role")
    ap.add_argument("--output", type=Path)
    args = ap.parse_args(argv)
    report = interaction_coverage(args.role_root)
    output = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(output, encoding="utf-8")
    else:
        print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

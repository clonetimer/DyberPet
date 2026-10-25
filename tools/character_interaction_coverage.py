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
from tools.genshin_library import scan_genshin_library
from tools.mascot_library import scan_mascot_library

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
    genshin = genshin_snapshot if genshin_snapshot is not None else scan_genshin_library(root)
    mascots = mascot_snapshot if mascot_snapshot is not None else scan_mascot_library(root)
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

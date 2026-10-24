#!/usr/bin/env python3
"""Batch-create Genshin character *cases*, never artwork, in the mature pipeline.

The roster and item-specific source registry are the sole inputs. This tool
does not crawl, download, import games' assets, attest rights, run Blender,
convert or package a character. Cases are user-local and initially blocked
until an authorized asset is attached and explicitly rights-reviewed.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__:
    from .genshin_roster import GENSHIN_ROSTER
    from .character_pipeline import (DEFAULT_WORKSPACE, PipelineError,
                                      dump_json, init_case, record_path, registry)
else:
    from genshin_roster import GENSHIN_ROSTER
    from character_pipeline import (DEFAULT_WORKSPACE, PipelineError,
                                    dump_json, init_case, record_path, registry)


def catalogue():
    rows = {}
    for item in registry()["candidates"]:
        profile = item.get("profile")
        if profile in ("genshin_" + key for key in GENSHIN_ROSTER):
            if profile in rows:
                raise PipelineError("Duplicate Genshin candidate profile: " + profile)
            rows[profile] = item
    if set(rows) != {"genshin_" + key for key in GENSHIN_ROSTER}:
        raise PipelineError("Genshin source registry and profile roster are inconsistent")
    return rows


def select_roles(raw: str):
    raw = (raw or "").strip()
    if raw.lower() == "all":
        return tuple(GENSHIN_ROSTER)
    ids = tuple(v.strip() for v in raw.split(",") if v.strip())
    if not ids or len(ids) != len(set(ids)):
        raise PipelineError("Select nonempty, unique role IDs or all")
    if any(key not in GENSHIN_ROSTER for key in ids):
        raise PipelineError("Unrecognized Genshin IDs: " +
                            ", ".join(k for k in ids if k not in GENSHIN_ROSTER))
    return ids


def plan(workspace, keys):
    catalog = catalogue()
    planned = []
    for key in keys:
        role = GENSHIN_ROSTER[key]
        candidate = catalog["genshin_" + key]
        source = candidate.get("asset_url", "")
        if role["source_work_url"] != source:
            raise PipelineError("Conflicting item-specific discovery source: " + key)
        case_id = candidate["id"]
        target = record_path(workspace, case_id)
        if target.is_symlink():
            raise PipelineError("Candidate file cannot be a symlink: " + case_id)
        planned.append({
            "id": case_id,
            "profile": "genshin_" + key,
            "character": role["name"],
            "channel": candidate["channel"],
            "source_url": source,
            "kind": candidate["kind_suggestion"],
            "needs_source_research": not bool(source),
            "case_exists": target.exists(),
            "rights": "NOT_REVIEWED",
            "playable_role_created": False,
            "publishable": False,
            "visual_checks": list(role["visual_checks"]),
            "motion_checks": list(role["motion_checks"]),
        })
    return planned


def seed(workspace, keys, *, dry_run=False):
    workspace = Path(workspace).expanduser().resolve()
    result = plan(workspace, keys)
    # Avoid partially creating a batch when any candidate ID already exists.
    # Also inspect all sidecars BEFORE writing anything.
    if not dry_run:
        for row in result:
            sidecar = workspace / "reviews" / (row["id"] + ".json")
            if sidecar.exists() or sidecar.is_symlink():
                raise FileExistsError("Review checklist already exists: " +
                                      sidecar.name)
    existing = [item["id"] for item in result if item["case_exists"]]
    if existing and not dry_run:
        raise FileExistsError("Existing candidates; no files modified: " +
                              ", ".join(existing))
    if dry_run:
        return {"mode": "preview", "cases": result, "created": 0}
    created = []
    try:
        for row in result:
            case = init_case(
                workspace, row["id"], row["character"], row["channel"],
                row["source_url"], row["kind"], row["profile"])
            created.append(case)
            # Checklist contains no art or inferred license. No author is
            # invented, and passing criteria never grants redistribution.
            checklist = workspace / "reviews" / (row["id"] + ".json")
            if checklist.exists() or checklist.is_symlink():
                raise FileExistsError("Review checklist already exists: " +
                                      checklist.name)
            dump_json({
                "candidate": row["id"], "profile": row["profile"],
                "character": row["character"], "artwork_available": False,
                "license_verification": "required_before_local_build",
                "redistribution_approval": False,
                "human_visual_checks": row["visual_checks"],
                "human_motion_checks": row["motion_checks"],
                "required_stages": [
                    "find specific author work",
                    "attach local original artwork and fingerprint",
                    "review local-use/derivative permissions",
                    "convert/import in existing pipeline",
                    "verify native Qt sprite loader and motion",
                    "review release rights separately before packaging",
                ],
                "visual_pass": False, "runtime_pass": False,
            }, checklist)
            created.append(checklist)
    except Exception:
        # Only delete files this invocation successfully created. Do not
        # remove, edit or overwrite pre-existing user resources.
        for file in reversed(created):
            if file.is_file() and not file.is_symlink():
                file.unlink()
        raise
    return {"mode": "seeded", "cases": result, "created": len(result),
            "workspace": str(workspace)}


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (OSError, ValueError):
                pass
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="List 14 asset-free character candidates")
    p = sub.add_parser("preview", help="Inspect batch before any local write")
    p.add_argument("--roles", default="all", help="all or comma-separated IDs")
    p = sub.add_parser("seed", help="Create local unapproved candidate records")
    p.add_argument("--roles", default="all", help="all or comma-separated IDs")
    args = parser.parse_args(argv)
    try:
        if args.command == "list":
            output = {
                key: {"name": role["name"], "profile": "genshin_" + key,
                      "source_known": bool(role["source_work_url"]),
                      "rights_verified": False, "playable": False}
                for key, role in GENSHIN_ROSTER.items()
            }
        else:
            keys = select_roles(args.roles)
            output = seed(args.workspace, keys, dry_run=args.command == "preview")
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0
    except (PipelineError, ValueError, FileExistsError, OSError) as exc:
        parser.exit(1, "Genshin batch blocked: " + str(exc) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())

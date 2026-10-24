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
                                      dump_json, init_case, record_path, registry,
                                      load_case, inspect_case, identify_local,
                                      fingerprint)
else:
    from genshin_roster import GENSHIN_ROSTER
    from character_pipeline import (DEFAULT_WORKSPACE, PipelineError,
                                    dump_json, init_case, record_path, registry,
                                    load_case, inspect_case, identify_local,
                                      fingerprint)


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
        if case_id != "genshin_" + key + "_main":
            raise PipelineError("Unexpected candidate ID for " + key)
        if candidate["rights_status"] != "unknown":
            raise PipelineError("Batch seed cannot assert item-level author permission")
        target = record_path(workspace, case_id)
        if target.is_symlink():
            raise PipelineError("Candidate file cannot be a symlink: " + case_id)
        planned.append({
            "id": case_id,
            "profile": "genshin_" + key,
            "character": role["name"],
            "channel": candidate["channel"],
            "source_url": source,
            "creator": candidate.get("creator", ""),
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
    # The workspace can be user-controlled. Do not follow a linked
    # cases/reviews directory when emitting evidence files.
    if (workspace / "cases").is_symlink() or (workspace / "reviews").is_symlink():
        raise PipelineError("Linked cases/reviews directory is not permitted")
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
                row["source_url"], row["kind"], row["profile"],
                row["creator"])
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




def seed_missing(workspace, keys):
    """Create only missing candidate pairs, preserving *all* earlier reviews.

    Existing case+review pairs are accepted only if their identities match the
    selected roster. An incomplete pair is an error, not permission to repair or
    overwrite a user's audit trail.
    """
    workspace = Path(workspace).expanduser().resolve()
    if (workspace / "cases").is_symlink() or (workspace / "reviews").is_symlink():
        raise PipelineError("Linked cases/reviews directory is not permitted")
    rows = plan(workspace, keys)
    missing, preserved = [], []
    for key, row in zip(keys, rows):
        case_file = record_path(workspace, row["id"])
        review_file = workspace / "reviews" / (row["id"] + ".json")
        if (case_file.is_symlink() or review_file.is_symlink() or
                (case_file.exists() and not case_file.is_file()) or
                (review_file.exists() and not review_file.is_file())):
            raise PipelineError("Unsafe case or review path: " + row["id"])
        if case_file.exists() != review_file.exists():
            raise PipelineError("Incomplete case/review pair: " + row["id"])
        if not case_file.exists():
            missing.append(key)
            continue
        case = load_case(case_file)
        review = json.loads(review_file.read_text(encoding="utf-8"))
        if (not isinstance(review, dict) or
                case.get("id") != row["id"] or
                case.get("profile") != row["profile"] or
                review.get("candidate") != row["id"] or
                review.get("profile") != row["profile"]):
            raise PipelineError("Existing candidate identity mismatch: " + row["id"])
        preserved.append(row["id"])
    if missing:
        # seed() preflights all missing case and checklist paths before writing.
        created = seed(workspace, tuple(missing))
        new_rows = created["cases"]
    else:
        new_rows = []
    return {
        "mode": "seed_missing",
        "total_selected": len(rows),
        "created": len(new_rows),
        "preserved": len(preserved),
        "created_ids": [row["id"] for row in new_rows],
        "preserved_ids": preserved,
        "workspace": str(workspace),
    }


def status(workspace, keys):
    """Read-only progress board backed by *actual* local candidate states."""
    workspace = Path(workspace).expanduser()
    # Status must be safe on user-owned workspaces too: never traverse
    # linked intake/review directories or individual linked case files.
    if (workspace / "cases").is_symlink() or (workspace / "reviews").is_symlink():
        raise PipelineError("Linked cases/reviews directory is not permitted")
    rows = []
    for expected in plan(workspace, keys):
        row = {
            "id": expected["id"], "character": expected["character"],
            "source_known": bool(expected["source_url"]),
            "case_exists": expected["case_exists"],
            "playable_role_verified": False,
            "redistribution_verified": False,
        }
        if not expected["case_exists"]:
            row["stage"] = "not_seeded"
            row["next_step"] = "seed candidate"
        else:
            case_path = record_path(workspace, expected["id"])
            if case_path.is_symlink():
                raise PipelineError("Linked candidate is not permitted: " + expected["id"])
            case = load_case(case_path)
            if (case["id"] != expected["id"] or
                    case.get("profile") != "genshin_" + expected["id"].removeprefix("genshin_").removesuffix("_main")):
                raise PipelineError("Candidate identity/profile mismatch: " + expected["id"])
            audit = inspect_case(case_path)
            if case["status"] == "packaged":
                row["stage"] = "packaged_locally"
                row["next_step"] = "verify package distribution policies independently"
            elif case["status"] == "qa_reviewed":
                row["stage"] = "qa_reviewed"
                row["next_step"] = "check redistribution rights before package"
            elif case["status"] == "built":
                row["stage"] = "built_pending_visual_runtime_qa"
                row["next_step"] = "complete human visual and running Qt QA"
            elif case["status"] == "rights_reviewed":
                row["stage"] = "rights_reviewed"
                row["next_step"] = "run existing guarded build"
            elif case["status"] == "source_attached":
                row["stage"] = "source_attached"
                row["next_step"] = "review actual asset rights, not source video alone"
            else:
                row["stage"] = "awaiting_local_artwork"
                row["next_step"] = "find specific source and attach local licensed asset"
            # QA flags alone are insufficient: the original may be missing,
            # modified since intake, or the built role may not exist.
            local_blockers = [issue for issue in audit["blockers"]
                              if "redistribution" not in issue]
            built_role = case["build"].get("role") or ""
            # Use the same role digest recorded at QA. Stale QA flags
            # alone must never imply a still-intact, approved build.
            role_dir = Path(built_role) if built_role else None
            build_root = (workspace.resolve() / "build" / case["id"]).resolve()
            safe_role = bool(
                role_dir and not role_dir.is_symlink() and
                role_dir.resolve().is_relative_to(build_root) and
                role_dir.is_dir())
            role_matches_qa = bool(
                safe_role and case["qa"].get("asset_sha256") and
                fingerprint(role_dir) == case["qa"]["asset_sha256"])
            row["playable_role_verified"] = bool(
                case["status"] in ("qa_reviewed", "packaged") and
                case["qa"]["visual_pass"] and case["qa"]["runtime_pass"] and
                role_matches_qa and not local_blockers)
            # This flag only reflects *recorded* human review, not an
            # independent legal assessment or permission to redistribute.
            row["redistribution_verified"] = bool(
                row["playable_role_verified"] and
                case["rights"]["redistribution"] and
                case["rights"]["reviewer"] and
                case["rights"]["evidence"])
            row["blocking_issue_count"] = len(audit["blockers"])
        rows.append(row)
    return {"mode": "status", "characters": rows,
            "counts": {
                "total": len(rows),
                "seeded": sum(v["case_exists"] for v in rows),
                "qa_verified": sum(v["playable_role_verified"] for v in rows),
                "locally_packaged": sum(v["stage"] == "packaged_locally"
                                       for v in rows),
            }}


def probe_asset(asset):
    """Non-mutating identification of a *single* local role source.

    A ZIP of an entire old executable release must not be mistaken for a MOD.
    Caller decides which Genshin person the art represents and checks rights.
    """
    import zipfile
    if __package__:
        from .install_native_role import inspect_zip, inspect_native_folder
    else:
        from install_native_role import inspect_zip, inspect_native_folder
    original = Path(asset).expanduser()
    if original.is_symlink():
        raise PipelineError("Symlinked artwork path is not permitted")
    source = original.resolve()
    kind = identify_local(source)
    if kind == "native_folder":
        check = inspect_native_folder(source)
        info = {"actions": check["validation"]["actions"],
                "frames": check["validation"]["images"],
                "file_count": len(check["files"])}
    elif kind == "native_zip":
        try:
            with zipfile.ZipFile(source) as archive:
                files, prefix = inspect_zip(archive)
        except (zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
            raise PipelineError("Invalid or unsupported native role ZIP") from exc
        info = {"contained_role_folder": prefix.name,
                "file_count": len(files)}
    else:
        raise PipelineError(
            "Select a single native role ZIP, or extracted res/role/<character> folder; "
            "full application, mini-pet and model assets need different workflows")
    return {
        "mode": "read_only_probe", "kind": kind, "configuration": info,
        "playable_role_verified": False, "license_verified": False,
        "role_identity_verified": False, "asset_modified": False,
        "next_step": "attach to a matching candidate, review rights, build and run QA",
    }


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
    sub.add_parser("list", help="List asset-free character candidates")
    p = sub.add_parser("preview", help="Inspect batch before any local write")
    p.add_argument("--roles", default="all", help="all or comma-separated IDs")
    p = sub.add_parser("seed", help="Create local unapproved candidate records")
    p.add_argument("--roles", default="all", help="all or comma-separated IDs")
    p = sub.add_parser("seed-missing", help="Add only missing roles without altering approved local cases")
    p.add_argument("--roles", default="all", help="all or comma-separated IDs")
    p = sub.add_parser("status", help="Summarize actual local role approvals without writing")
    p.add_argument("--roles", default="all", help="all or comma-separated IDs")
    p = sub.add_parser("probe", help="Read-only structural preflight for one local original MOD")
    p.add_argument("--asset", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "list":
            output = {
                key: {"name": role["name"], "profile": "genshin_" + key,
                      "source_known": bool(role["source_work_url"]),
                      "rights_verified": False, "playable": False}
                for key, role in GENSHIN_ROSTER.items()
            }
        elif args.command == "probe":
            output = probe_asset(args.asset)
        elif args.command == "status":
            output = status(args.workspace, select_roles(args.roles))
        elif args.command == "seed-missing":
            output = seed_missing(args.workspace, select_roles(args.roles))
        else:
            keys = select_roles(args.roles)
            output = seed(args.workspace, keys, dry_run=args.command == "preview")
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0
    except (PipelineError, ValueError, FileExistsError, OSError, KeyError,
            json.JSONDecodeError) as exc:
        parser.exit(1, "Genshin batch blocked: " + str(exc) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())

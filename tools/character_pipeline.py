#!/usr/bin/env python3
"""Local-first character intake / build / QA / release pipeline for DyberPet.

No network calls, no scraping, no asset fetching, no unattended publication.
Every case remains in a git-ignored workspace unless its OWNER intentionally
copies it elsewhere. Third-party model files are never published by this tool.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

if __package__:
    from .chibi_profiles import CHIBI_PROFILES
    from .turnaround_gate import VIEWS, CHECKS, capture, approve, verify, release_metadata, TurnaroundError
else:
    from chibi_profiles import CHIBI_PROFILES
    from turnaround_gate import VIEWS, CHECKS, capture, approve, verify, release_metadata, TurnaroundError

KINDS = ("codex", "frames", "native_zip", "native_folder", "model3d")
ACTION_PLAN = ("idle", "left_walk", "right_walk", "wave", "jump",
               "wait", "sleep", "review")
ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]{2,47}$")
SOURCE_REGISTRY = Path(__file__).with_name("character_sources.json")
DEFAULT_WORKSPACE = Path(__file__).resolve().parents[1] / "data" / "character_pipeline"


class PipelineError(ValueError):
    pass


def utc_date():
    return dt.datetime.now(dt.timezone.utc).date().isoformat()


def dump_json(data, file):
    file = Path(file)
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")


def registry():
    data = json.loads(SOURCE_REGISTRY.read_text(encoding="utf-8"))
    assert data["schema_version"] == 1
    return data


def channel_ids():
    return {s["id"] for s in registry()["channels"]}


def record_path(workspace, role_id):
    if not ID_PATTERN.fullmatch(role_id):
        raise PipelineError("Invalid candidate id (lowercase letters, digits, _)")
    return Path(workspace).resolve() / "cases" / (role_id + ".json")


def init_case(workspace, role_id, name, source_channel, source_url,
              kind, profile=None, creator=None):
    if source_channel not in channel_ids():
        raise PipelineError("Unknown source channel; run sources command")
    if kind not in KINDS:
        raise PipelineError("Unsupported source kind: " + kind)
    if profile and profile not in CHIBI_PROFILES:
        raise PipelineError("Unknown Q-style character template")
    path = record_path(workspace, role_id)
    if path.exists():
        raise FileExistsError("Candidate exists: " + str(path))
    data = {
        "schema_version": 1, "id": role_id, "character": name,
        "profile": profile,
        "source": {"channel": source_channel, "url": source_url,
                   "artist": creator or "", "kind": kind,
                   "local_asset": "", "sha256": ""},
        "rights": {"evidence": "", "reviewer": "", "reviewed_on": "",
                   "local_use": False, "derivative_use": False,
                   "redistribution": False},
        "qa": {"reviewer": "", "reviewed_on": "", "visual_pass": False,
               "runtime_pass": False, "asset_sha256": ""},
        "status": "discovered", "build": {"role": "", "report": ""},
        "turnaround": {},
        "history": [{"date": utc_date(), "event": "discovered"}],
    }
    dump_json(data, path)
    return path


def load_case(case_file):
    path = Path(case_file).resolve()
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise PipelineError("Unsupported case schema")
    expected = record_path(path.parent.parent, data["id"])
    if expected != path:
        raise PipelineError("Case file must live at <workspace>/cases/<id>.json")
    if data["source"]["channel"] not in channel_ids():
        raise PipelineError("Unknown source channel in case file")
    if data["source"]["kind"] not in KINDS:
        raise PipelineError("Unsupported source kind")
    return data


def advance(data, event, **kwargs):
    data["history"].append({"date": utc_date(), "event": event, **kwargs})


def asset_path(data):
    raw = data["source"].get("local_asset") or ""
    return Path(raw).expanduser().resolve() if raw else None


def identify_local(path):
    path = Path(path)
    if path.is_file():
        ext = path.suffix.lower()
        if ext == ".zip":
            return "native_zip"
        if ext in (".pmx", ".pmd", ".vrm", ".blend", ".fbx", ".glb", ".gltf"):
            return "model3d"
        if ext in (".webp", ".png"):
            return "codex"
    if path.is_dir():
        if (path / "pet.json").is_file():
            return "codex"
        if (path / "pet_conf.json").is_file():
            return "native_folder"
        if any((path / x).is_file() for x in
               ("idle.gif", "idle.png", "idle.webp", "idle_0.png")):
            return "frames"
        if any(p.suffix.lower() in (".pmx", ".pmd", ".vrm",
                                    ".blend", ".fbx", ".glb", ".gltf")
               for p in path.iterdir() if p.is_file()):
            return "model3d"
    return "unknown"


def fingerprint(path):
    """Content hash for audit, not a network download or author proof."""
    path = Path(path).resolve()
    digest = hashlib.sha256()
    if path.is_file():
        with path.open("rb") as source:
            for part in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(part)
    elif path.is_dir():
        total = 0
        for file in sorted(path.rglob("*")):
            if file.is_symlink():
                raise PipelineError("Symlink not permitted in local artwork source")
            if not file.is_file():
                continue
            total += 1
            if total > 6000:
                raise PipelineError("Too many local asset files")
            digest.update(file.relative_to(path).as_posix().encode("utf-8"))
            with file.open("rb") as source:
                for part in iter(lambda: source.read(1024 * 1024), b""):
                    digest.update(part)
    else:
        raise PipelineError("No local source asset")
    return digest.hexdigest()


def attach_case(case_file, source):
    data = load_case(case_file)
    candidate = Path(source).expanduser()
    if candidate.is_symlink():
        raise PipelineError("Symlinked source asset is not permitted")
    target = candidate.resolve()
    if not target.exists():
        raise PipelineError("Artwork path does not exist")
    found = identify_local(target)
    expected = data["source"]["kind"]
    if found != expected:
        # Legacy GenshinImpact distributions may be an entire application.
        # The user must select an extracted single res/role/<name> directory.
        # Switching representation invalidates all earlier rights/QA below.
        if expected == "native_zip" and found == "native_folder":
            data["source"]["kind"] = found
        else:
            raise PipelineError(
                f"Expected {expected}, detected {found}; "
                "select an extracted original role folder or matching source kind"
            )
    data["source"]["local_asset"] = str(target)
    data["source"]["sha256"] = fingerprint(target)
    data["status"] = "source_attached"
    # A new source invalidates earlier permissions, author attestations and QA.
    data["rights"] = {"evidence": "", "reviewer": "", "reviewed_on": "",
                      "local_use": False, "derivative_use": False,
                      "redistribution": False}
    data["qa"] = {"reviewer": "", "reviewed_on": "", "visual_pass": False,
                  "runtime_pass": False, "asset_sha256": ""}
    data["build"] = {"role": "", "report": ""}
    if data.get("turnaround"):
        data["turnaround"]["review"] = {}  # different motion source: re-review likeness
    advance(data, "source_attached", kind=found)
    dump_json(data, case_file)
    return data


def attach_turnaround(case_file, *, front, side, back, reference_url, artist, variant):
    data = load_case(case_file)
    if data["status"] in ("built", "qa_reviewed", "packaged"):
        raise PipelineError("Use a new case ID rather than alter a built reference")
    data["turnaround"] = capture(front, side, back, reference_url=reference_url,
                                 artist=artist, variant=variant)
    advance(data, "turnaround_attached", variant=variant)
    dump_json(data, case_file)
    return data


def review_turnaround(case_file, reviewer, checks):
    data = load_case(case_file)
    if data["status"] in ("built", "qa_reviewed", "packaged"):
        raise PipelineError("Cannot revise turnaround approval after build")
    data["turnaround"] = approve(data.get("turnaround") or {},
                                 reviewer, checks, utc_date())
    advance(data, "turnaround_reviewed", reviewer=reviewer)
    dump_json(data, case_file)
    return data


def rights_review(case_file, reviewer, evidence, *,
                  local_use=False, derivatives=False, redistribution=False):
    data = load_case(case_file)
    if not reviewer.strip() or not evidence.strip():
        raise PipelineError("Reviewer and source-specific rights evidence required")
    if not (evidence.startswith(("https://", "http://", "file://")) or
            Path(evidence).is_file()):
        raise PipelineError("Evidence must be an accessible local file or explicit URL")
    data["rights"] = {
        "reviewer": reviewer, "evidence": evidence,
        "reviewed_on": utc_date(), "local_use": bool(local_use),
        "derivative_use": bool(derivatives),
        "redistribution": bool(redistribution),
    }
    data["status"] = "rights_reviewed"
    advance(data, "rights_reviewed", reviewer=reviewer,
            local_use=bool(local_use), derivative_use=bool(derivatives),
            redistribution=bool(redistribution))
    dump_json(data, case_file)
    return data


def check_build_gate(data):
    source = asset_path(data)
    if source is None or not source.exists():
        raise PipelineError("Attach a local asset first")
    if data["source"]["sha256"] != fingerprint(source):
        raise PipelineError("Source files changed since intake; attach again and re-review")
    if not data["rights"]["reviewer"] or not data["rights"]["evidence"]:
        raise PipelineError("Human rights review with evidence required before build")
    if not data["rights"]["local_use"]:
        raise PipelineError("No permission recorded for local use")
    if data["source"]["kind"] in ("codex", "frames") and not data["rights"]["derivative_use"]:
        raise PipelineError("Conversion requires acknowledged permission to create derivatives")
    if data["source"]["kind"] == "model3d":
        raise PipelineError("3D source requires render plan and local Blender/MMD rendering first")
    verify(data.get("turnaround"))
    return source


def create_render_plan(case_file):
    data = load_case(case_file)
    if data["source"]["kind"] != "model3d":
        raise PipelineError("Render plans are only for 3D models")
    target = Path(case_file).resolve().parent.parent / "plans" / (data["id"] + ".json")
    plan = {
        "candidate": data["id"], "source": data["source"]["url"],
        "format": "3D source; NOT directly playable by DyberPet",
        "rights_evidence": data["rights"]["evidence"],
        "requirements": {
            "manual_tools": ["MMD/Blender or authorized equivalent",
                             "Model-specific import plugin where required"],
            "render": "transparent RGBA; consistent orthographic camera; 192x208 canvas preferred",
            "timings": "stable frame rate or per-action GIF delays",
            "actions": list(ACTION_PLAN),
            "output_folder": "idle_0.png, idle_1.png; left_walk_0.png; ...",
            "notes": [
                "Obtain permission for modifying and rendering the model and any motion data",
                "MMD PMX is NOT automatically imported by Pillow or by this pipeline",
                "No protected game assets are automatically fetched",
                "Render each action locally, then open a new kind=frames pipeline case",
                "Keep model and motion attributions in the rights evidence",
            ],
        },
    }
    dump_json(plan, target)
    return target


def render_3d_case(case_file, *, blender="blender", frames=6,
                   actions=("idle", "left_walk", "right_walk", "wave",
                            "jump", "wait", "review"), timeout=600,
                   frames_case_id=None, require_clips=False, clip_map=None):
    """Render an approved local GLB/FBX into a *new* unapproved frames case.

    This is deliberately not equivalent to a successful role build or rights
    clearance. The child frames case requires a second human rights review
    before it may become an installed role or published ZIP.
    """
    data = load_case(case_file)
    if data["source"]["kind"] != "model3d":
        raise PipelineError("Only model3d candidates may use render")
    source = asset_path(data)
    if source is None or not source.is_file():
        raise PipelineError("Attach one local 3D model file first")
    if data["source"]["sha256"] != fingerprint(source):
        raise PipelineError("3D source changed after intake; attach and review again")
    rights = data["rights"]
    if not (rights["reviewer"] and rights["evidence"] and
            rights["local_use"] and rights["derivative_use"]):
        raise PipelineError(
            "3D rendering needs author-specific human rights evidence "
            "and permission for local use and derivatives"
        )
    child_id = frames_case_id or data["id"] + "_frames"
    root = Path(case_file).resolve().parent.parent
    child_path = record_path(root, child_id)
    if child_path.exists():
        raise FileExistsError("Derived frames candidate already exists")
    output_root = root / "renders" / data["id"]
    if output_root.exists():
        raise FileExistsError("Render output already exists, no overwrite allowed")
    if __package__:
        from .render_chibi_blender import render_blender
    else:
        from render_chibi_blender import render_blender
    try:
        render_options = dict(source=source, frames=frames,
                              actions=tuple(actions), timeout=timeout)
        if require_clips:
            render_options["require_clips"] = True
        if clip_map is not None:
            render_options["clip_map"] = clip_map
        rendered = render_blender(blender, output_root, **render_options)
        if fingerprint(source) != data["source"]["sha256"]:
            raise PipelineError("3D source changed during Blender render")
        child = init_case(
            root, child_id, data["character"], data["source"]["channel"],
            data["source"]["url"], "frames", data.get("profile"),
            data["source"]["artist"]
        )
        child_data = attach_case(child, rendered)
        child_data["derived_from"] = {
            "parent_case": data["id"],
            "parent_asset_sha256": data["source"]["sha256"],
            "render_report": str(rendered / "BLENDER_RENDER_REPORT.json")
        }
        dump_json(child_data, child)
    except Exception:
        # Do not leave an apparently usable unreviewed render after failure.
        if output_root.is_dir():
            shutil.rmtree(output_root)
        raise
    data["status"] = "rendered"
    data["render"] = {"frames_case": child_id, "render_path": str(output_root)}
    advance(data, "rendered_to_frames_candidate", child_id=child_id)
    dump_json(data, case_file)
    return child_path


def build_case(case_file):
    data = load_case(case_file)
    source = check_build_gate(data)
    root = Path(case_file).resolve().parent.parent
    output_root = root / "build" / data["id"]
    if output_root.exists() and any(output_root.iterdir()):
        raise PipelineError("Build output exists; use a new case ID or archive and clear it")
    kind = data["source"]["kind"]
    # Writes only into the gitignored pipeline workspace, not installed roles.
    if kind == "codex":
        if __package__:
            from .import_codex_pet import convert
        else:
            from import_codex_pet import convert
        role = convert(source, output_root, folder="ChibiPipelineRole",
                       profile=data.get("profile"), style="chibi",
                       name=data["character"], author=data["source"]["artist"],
                       license_name="See candidate-specific rights evidence",
                       source_url=data["source"]["url"])
    elif kind == "frames":
        if __package__:
            from .import_chibi_animations import convert_animation_folder
        else:
            from import_chibi_animations import convert_animation_folder
        role = convert_animation_folder(
            source, output_root, folder="ChibiPipelineRole",
            profile=data.get("profile"), name=data["character"],
            author=data["source"]["artist"],
            license_name="See candidate-specific rights evidence",
            source_url=data["source"]["url"])
    elif kind == "native_zip":
        if __package__:
            from .install_native_role import install_native_role
        else:
            from install_native_role import install_native_role
        role = install_native_role(source, output_root,
                                   role_folder="ChibiPipelineRole")
    elif kind == "native_folder":
        if __package__:
            from .install_native_role import install_native_folder
        else:
            from install_native_role import install_native_folder
        role = install_native_folder(source, output_root,
                                     role_folder="ChibiPipelineRole")
    else:
        raise PipelineError("Unsupported build source kind")
    if __package__:
        from .install_native_role import validate_native_role
    else:
        from install_native_role import validate_native_role
    try:
        preflight = validate_native_role(role)
        if fingerprint(source) != data["source"]["sha256"]:
            raise PipelineError("Source changed while building; reattach and re-review")
        (role / "PIPELINE_SOURCE.json").write_text(
            json.dumps({"candidate": data["id"],
                        "channel": data["source"]["channel"],
                        "asset_url": data["source"]["url"],
                        "author": data["source"]["artist"],
                        "rights_evidence": data["rights"]["evidence"],
                        "input_sha256": data["source"]["sha256"],
                        "turnaround": release_metadata(data["turnaround"]),
                        "preflight": preflight},
                       ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
    except Exception:
        shutil.rmtree(role, ignore_errors=True)
        raise
    data["build"] = {"role": str(role), "report": str(role / "PIPELINE_SOURCE.json")}
    data["qa"] = {"reviewer": "", "reviewed_on": "", "visual_pass": False,
                  "runtime_pass": False, "asset_sha256": ""}
    data["status"] = "built"
    advance(data, "built", frame_files=preflight["images"])
    dump_json(data, case_file)
    return role


def qa_review(case_file, reviewer, *, visual_pass=False, runtime_pass=False):
    data = load_case(case_file)
    role = Path(data["build"].get("role") or "")
    if data["status"] not in ("built", "qa_reviewed"):
        raise PipelineError("Build the candidate before visual/runtime QA")
    if not role.is_dir():
        raise PipelineError("Built role not found")
    if not reviewer.strip():
        raise PipelineError("Human QA reviewer required")
    if not visual_pass or not runtime_pass:
        raise PipelineError("Both visual and real DyberPet runtime checks must pass")
    verify(data.get("turnaround"))
    data["qa"] = {"reviewer": reviewer, "reviewed_on": utc_date(),
                  "visual_pass": True, "runtime_pass": True,
                  "asset_sha256": fingerprint(role)}
    data["status"] = "qa_reviewed"
    advance(data, "qa_reviewed", reviewer=reviewer)
    dump_json(data, case_file)
    return data


def package_release(case_file):
    data = load_case(case_file)
    if data["status"] != "qa_reviewed":
        raise PipelineError("Release blocked: human visual AND runtime QA not approved")
    rights, qa = data["rights"], data["qa"]
    if not (rights["reviewer"] and rights["evidence"] and
            rights["redistribution"] and rights["derivative_use"]):
        raise PipelineError("Release blocked: rights review does not permit redistribution/derivatives")
    if not (qa["visual_pass"] and qa["runtime_pass"]):
        raise PipelineError("Release blocked: mandatory QA missing")
    if not qa["reviewer"]:
        raise PipelineError("Release blocked: missing QA reviewer")
    verify(data.get("turnaround"))
    role = Path(data["build"]["role"]).resolve()
    if not role.is_dir() or fingerprint(role) != qa["asset_sha256"]:
        raise PipelineError("Built role changed since QA approval")
    output = Path(case_file).resolve().parent.parent / "releases" / (data["id"] + ".zip")
    if output.exists():
        raise FileExistsError("Local release package already exists; refusing overwrite")
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED) as zipf:
        for path in sorted(role.rglob("*")):
            if path.is_file():
                zipf.write(path, str(Path(data["id"]) / path.relative_to(role)))
    data["status"] = "packaged"
    advance(data, "packaged_locally", name=output.name)
    dump_json(data, case_file)
    return output


def inspect_case(case_file):
    data = load_case(case_file)
    problems = []
    source = asset_path(data)
    if source is None or not source.exists():
        problems.append("missing local source")
    elif fingerprint(source) != data["source"]["sha256"]:
        problems.append("source changed; attach again")
    rights = data["rights"]
    if not rights["reviewer"] or not rights["evidence"]:
        problems.append("no item-specific rights evidence")
    if not rights["local_use"]:
        problems.append("local usage not authorized by reviewer")
    if data["source"]["kind"] in ("codex", "frames") and not rights["derivative_use"]:
        problems.append("image conversion/derivative use not authorized")
    if data["source"]["kind"] == "model3d":
        problems.append("3D asset requires separate authorized transparent rendering")
    try:
        verify(data.get("turnaround"))
    except TurnaroundError as exc:
        problems.append(str(exc))
    if not data["qa"]["visual_pass"] or not data["qa"]["runtime_pass"]:
        problems.append("real visual/runtime QA not complete")
    if not rights["redistribution"]:
        problems.append("redistribution not authorized; do not publish images")
    return {"candidate": data["id"], "status": data["status"],
            "source_channel": data["source"]["channel"],
            "format": data["source"]["kind"], "blockers": problems,
            "next_step": ("render model to local transparent PNG/GIF"
                          if data["source"]["kind"] == "model3d"
                          else "review rights, then build, QA and package")}


def main(argv=None):
    # On Windows CI / redirected PowerShell, stdout may default to cp1252.
    # Displaying Chinese registry names must not abort a read-only audit.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (OSError, ValueError):
                pass
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE,
                   help="Local workspace; default is gitignored data/character_pipeline")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("sources", help="List supported discovery channels; no web scraping")
    a = sub.add_parser("new", help="Create a source candidate record")
    a.add_argument("id")
    a.add_argument("--name", required=True)
    a.add_argument("--channel", required=True, choices=sorted(channel_ids()))
    a.add_argument("--url", default="")
    a.add_argument("--kind", choices=KINDS, required=True)
    a.add_argument("--profile", choices=sorted(CHIBI_PROFILES))
    a.add_argument("--creator")
    a = sub.add_parser("attach", help="Record source asset and its content hash")
    a.add_argument("id")
    a.add_argument("--asset", type=Path, required=True)
    a = sub.add_parser("turnaround-attach", help="Attach front/side/back Q-chibi reference")
    a.add_argument("id")
    for view in VIEWS:
        a.add_argument("--" + view, type=Path, required=True)
    a.add_argument("--reference-url", required=True)
    a.add_argument("--artist", required=True)
    a.add_argument("--variant", required=True)
    a = sub.add_parser("turnaround-review", help="Human approve Q-chibi visual consistency")
    a.add_argument("id")
    a.add_argument("--reviewer", required=True)
    for check in CHECKS:
        a.add_argument("--" + check, action="store_true")
    a = sub.add_parser("rights", help="Record user-performed item-specific license check")
    a.add_argument("id")
    a.add_argument("--reviewer", required=True)
    a.add_argument("--evidence", required=True)
    a.add_argument("--local-use", action="store_true")
    a.add_argument("--derivatives", action="store_true")
    a.add_argument("--redistribution", action="store_true")
    for command in ("inspect", "render-plan", "render", "build", "qa", "package"):
        a = sub.add_parser(command)
        a.add_argument("id")
        if command == "render":
            a.add_argument("--blender", default="blender")
            a.add_argument("--frames", type=int, default=6)
            a.add_argument("--actions", default="idle,left_walk,right_walk,wave,jump,wait,review")
            a.add_argument("--timeout", type=int, default=600)
            a.add_argument("--require-clips", action="store_true")
            a.add_argument("--clip-map", type=Path)
            a.add_argument("--frames-case-id")
        if command == "qa":
            a.add_argument("--reviewer", required=True)
            a.add_argument("--visual-pass", action="store_true")
            a.add_argument("--runtime-pass", action="store_true")
    args = p.parse_args(argv)
    try:
        if args.command == "sources":
            output = registry()
        elif args.command == "new":
            output = str(init_case(args.workspace, args.id, args.name, args.channel,
                                   args.url, args.kind, args.profile, args.creator))
        else:
            case = record_path(args.workspace, args.id)
            if args.command == "attach":
                output = attach_case(case, args.asset)["status"]
            elif args.command == "turnaround-attach":
                output = attach_turnaround(
                    case, front=args.front, side=args.side, back=args.back,
                    reference_url=args.reference_url, artist=args.artist,
                    variant=args.variant)["turnaround"]["variant"]
            elif args.command == "turnaround-review":
                output = review_turnaround(
                    case, args.reviewer, {k: getattr(args, k) for k in CHECKS})["turnaround"]["review"]["reviewed_on"]
            elif args.command == "rights":
                output = rights_review(
                    case, args.reviewer, args.evidence,
                    local_use=args.local_use, derivatives=args.derivatives,
                    redistribution=args.redistribution)["status"]
            elif args.command == "inspect":
                output = inspect_case(case)
            elif args.command == "render-plan":
                output = str(create_render_plan(case))
            elif args.command == "render":
                output = str(render_3d_case(
                    case, blender=args.blender, frames=args.frames,
                    actions=tuple(a.strip() for a in args.actions.split(",")),
                    timeout=args.timeout, frames_case_id=args.frames_case_id,
                    require_clips=args.require_clips, clip_map=args.clip_map
                ))
            elif args.command == "build":
                output = str(build_case(case))
            elif args.command == "qa":
                output = qa_review(case, args.reviewer, visual_pass=args.visual_pass,
                                   runtime_pass=args.runtime_pass)["status"]
            elif args.command == "package":
                output = str(package_release(case))
        print(json.dumps(output, ensure_ascii=False, indent=2)
              if isinstance(output, (dict, list)) else output)
        return 0
    except (PipelineError, FileNotFoundError, FileExistsError, OSError,
            ValueError, json.JSONDecodeError, zipfile.BadZipFile) as exc:
        p.exit(1, f"Pipeline blocked: {exc}\n")


if __name__ == "__main__":
    sys.exit(main())

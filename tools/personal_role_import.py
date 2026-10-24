#!/usr/bin/env python3
"""Offline, *private* installation of user-supplied character art.

No redistributable package, remote fetch, license attestation, or portfolio
claim. The person importing must assess the rules for the particular asset;
personal/non-commercial use is not a universal license.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from pathlib import Path

try:
    from .chibi_profiles import CHIBI_PROFILES, available_role_folder
    from .character_pipeline import PipelineError, fingerprint, identify_local
    from .import_chibi_animations import resolve_animations
    from .install_native_role import (BLOCKED_SUFFIXES, MAX_FILES, MAX_SINGLE_FILE,
                                      MAX_TOTAL_SIZE, inspect_native_folder, inspect_zip,
                                      install_native_folder, install_native_role,
                                      validate_native_role)
except ImportError:  # directly runnable from tools/ on Windows
    from chibi_profiles import CHIBI_PROFILES, available_role_folder
    from character_pipeline import PipelineError, fingerprint, identify_local
    from import_chibi_animations import resolve_animations
    from install_native_role import (BLOCKED_SUFFIXES, MAX_FILES, MAX_SINGLE_FILE,
                                     MAX_TOTAL_SIZE, inspect_native_folder, inspect_zip,
                                     install_native_folder, install_native_role,
                                     validate_native_role)


def inspect_personal_asset(source):
    """A read-only, bounded inspection. Never trust a file's extension alone."""
    provided = Path(source).expanduser()
    if provided.is_symlink():
        raise PipelineError("Linked source paths are not accepted")
    source = provided.resolve()
    if not source.exists():
        raise PipelineError("Choose a local character source that exists")
    kind = identify_local(source)
    if kind not in ("native_zip", "native_folder", "frames", "codex"):
        raise PipelineError("Only one native ZIP/folder, Codex folder or idle GIF/PNG folder is supported; 3D must be rendered first")
    meta = {}
    if kind == "native_zip":
        try:
            with zipfile.ZipFile(source) as archive:
                files, prefix = inspect_zip(archive)
        except (zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
            raise PipelineError("Invalid or unsupported character ZIP") from exc
        meta = {"source_members": len(files), "role_root": prefix.name}
    elif kind == "native_folder":
        result = inspect_native_folder(source)
        meta = {"source_members": len(result["files"]),
                "actions": result["validation"]["actions"],
                "frames": result["validation"]["images"]}
    else:
        if not source.is_dir():
            raise PipelineError("Choose the extracted Codex or GIF/PNG animation folder")
        n, size = 0, 0
        for item in source.rglob("*"):
            if item.is_symlink():
                raise PipelineError("Linked files are not supported in private imports")
            if item.is_file():
                n += 1
                size += item.stat().st_size
                if item.suffix.lower() in BLOCKED_SUFFIXES:
                    raise PipelineError("Source contains an executable or script")
                if (item.stat().st_size > MAX_SINGLE_FILE or
                        n > MAX_FILES or size > MAX_TOTAL_SIZE):
                    raise PipelineError("Local character source exceeds safe limits")
        if kind == "frames":
            actions, warnings = resolve_animations(source)
            meta = {"source_members": n, "detected_actions": sorted(actions),
                    "warnings": warnings}
        else:
            # Validity of the atlas/manifest is checked by the real converter.
            if not (source / "pet.json").is_file():
                raise PipelineError("Codex folder must contain pet.json")
            meta = {"source_members": n, "codex_manifest": True}
    return {"kind": kind, "source": source, "details": meta,
            "rights_verified": False, "publishable": False}


def personal_install(source, output_root, *, profile=None,
                     confirm_local_only=False, folder=None):
    """Install only to caller's local role directory, with no publish path."""
    if not confirm_local_only:
        raise PipelineError("Explicit --personal-use acknowledgement required")
    if profile is not None and profile not in CHIBI_PROFILES:
        raise PipelineError("Unknown Q-style template: " + str(profile))
    if folder is not None and not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,39}", folder):
        raise PipelineError("Custom role folder must be safe ASCII, <=40 characters")
    info = inspect_personal_asset(source)
    root = Path(output_root).expanduser()
    if root.is_symlink():
        raise PipelineError("Linked role root is not supported")
    root = root.resolve()
    source_path = info["source"]
    if info["kind"] != "native_zip" and (root == source_path or
                                         root.is_relative_to(source_path)):
        raise PipelineError("Output must not be inside the original source folder")
    # An existing candidate cannot be altered even when the source is trusted.
    destination_name = folder or available_role_folder(
        root, ("Personal" + "".join(word.title() for word in profile.split("_"))
               if profile else source_path.stem))
    destination = root / destination_name
    if destination.exists() or destination.is_symlink():
        raise FileExistsError("Local role already exists: " + destination_name)
    before_sha = fingerprint(source_path)
    if info["kind"] == "native_zip":
        new = install_native_role(source_path, root, role_folder=destination_name)
    elif info["kind"] == "native_folder":
        new = install_native_folder(source_path, root, role_folder=destination_name)
    elif info["kind"] == "codex":
        try:
            from .import_codex_pet import convert
        except ImportError:
            from import_codex_pet import convert
        new = convert(source_path, root, folder=destination_name, profile=profile,
                      style="chibi", license_name="Personal local import; rights not reviewed")
    else:
        try:
            from .import_chibi_animations import convert_animation_folder
        except ImportError:
            from import_chibi_animations import convert_animation_folder
        new = convert_animation_folder(source_path, root, folder=destination_name,
                                       profile=profile,
                                       license_name="Personal local import; rights not reviewed")
    # A successful local install is not a legal determination or actual human QA.
    # Preserve existing role on any post-install receipt problem? No: rollback
    # only the brand-new path from this transaction, never previous roles.
    try:
        if fingerprint(source_path) != before_sha:
            raise PipelineError("Source changed during private import; discard generated role")
        validation = validate_native_role(new)
        receipt = {
            "mode": "personal_local_only",
            "source_kind": info["kind"],
            "source_sha256": before_sha,
            "selected_profile": profile,
            "visual_identity_verified": False,
            "source_rights_verified": False,
            "redistribution_allowed_by_tool": False,
            "real_windows_qa_verified": False,
            "validation": validation,
            "notes": "Review the specific creator's terms. Do not redistribute this imported art by default.",
        }
        (new / "PERSONAL_IMPORT.json").write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
    except Exception:
        # Avoid deleting unexpected user files if a race replaced this path.
        # Installers use an atomic rename and choose an unused destination.
        if new == destination and new.is_dir() and not new.is_symlink():
            import shutil
            shutil.rmtree(new)
        raise
    return new


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (OSError, ValueError):
                pass
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    a = sub.add_parser("inspect", help="Read-only detection of a local asset")
    a.add_argument("--asset", type=Path, required=True)
    a = sub.add_parser("install", help="Install locally, never publish")
    a.add_argument("--asset", type=Path, required=True)
    a.add_argument("--output-root", type=Path,
                   default=Path(__file__).resolve().parents[1] / "res" / "role")
    a.add_argument("--profile", choices=sorted(CHIBI_PROFILES))
    a.add_argument("--folder")
    a.add_argument("--personal-use", action="store_true",
                   help="Acknowledge that you chose this source for private local use; not a license grant")
    args = p.parse_args(argv)
    try:
        if args.command == "inspect":
            result = inspect_personal_asset(args.asset)
            output = {"kind": result["kind"], **result["details"],
                      "rights_verified": False, "publishable": False}
        else:
            installed = personal_install(args.asset, args.output_root,
                                         profile=args.profile,
                                         confirm_local_only=args.personal_use,
                                         folder=args.folder)
            output = {"installed": installed.name, "scope": "local_only",
                      "rights_verified": False, "redistribution_enabled": False}
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0
    except (PipelineError, ValueError, FileNotFoundError, FileExistsError,
            OSError, ImportError, zipfile.BadZipFile) as exc:
        p.exit(1, "Private install blocked: " + str(exc) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())

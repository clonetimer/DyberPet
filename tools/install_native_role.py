#!/usr/bin/env python3
"""Install an existing DyberPet character ZIP locally without overwriting roles.

For trusted third-party role MOD archives, not a downloader. ZIP files may
contain artwork with separate rights; installation never grants redistribution.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import stat
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

if __package__:
    from .chibi_profiles import available_role_folder
else:
    from chibi_profiles import available_role_folder

MAX_FILES = 6000
MAX_SINGLE_FILE = 64 * 1024 * 1024
MAX_TOTAL_SIZE = 1200 * 1024 * 1024
BLOCKED_SUFFIXES = {".exe", ".dll", ".bat", ".cmd", ".ps1", ".vbs",
                    ".py", ".pyc", ".sh", ".so", ".dylib", ".com", ".scr", ".lnk"}


def inspect_zip(archive: zipfile.ZipFile):
    selected, size = [], 0
    for member in archive.infolist():
        path = PurePosixPath(member.filename.replace("\\", "/"))
        if (not member.filename or member.filename.startswith(("/", "\\")) or
                re.match(r"^[A-Za-z]:", member.filename) or
                any(part in ("..", "") for part in path.parts)):
            raise ValueError("Unsafe archive path: " + member.filename)
        if any(part in ("__MACOSX",) or part.startswith(".") for part in path.parts):
            continue
        unix_mode = (member.external_attr >> 16)
        file_kind = stat.S_IFMT(unix_mode)
        if file_kind not in (0, stat.S_IFREG, stat.S_IFDIR):
            raise ValueError("Links or special files are not supported")
        if member.is_dir():
            continue
        if path.suffix.lower() in BLOCKED_SUFFIXES:
            raise ValueError("Archive contains a blocked executable/script: " + str(path))
        if member.file_size > MAX_SINGLE_FILE:
            raise ValueError("One archive member exceeds maximum file size")
        size += member.file_size
        selected.append((member, path))
        if len(selected) > MAX_FILES or size > MAX_TOTAL_SIZE:
            raise ValueError("Archive exceeds safe extraction limits")
    roots = [p.parent for _, p in selected if p.name == "pet_conf.json"]
    # Support role files at root, RoleName/, and res/role/RoleName/.
    # Never guess when there is more than one role.
    roots = sorted(set(roots), key=str)
    if len(roots) != 1:
        raise ValueError("ZIP must contain exactly one DyberPet role with pet_conf.json")
    prefix = roots[0]
    # DyberPet mini companions live under res/pet, not res/role. They have
    # similar JSON filenames but use another loader and must not be installed
    # as a main character merely because the archive contains pet_conf.json.
    parts = prefix.parts
    if len(parts) >= 3 and parts[:2] == ("res", "pet"):
        raise ValueError(
            "This is a mini-pet companion pack (res/pet), not a main role. "
            "Use DyberPet's mini-pet management rather than Character Management."
        )
    if not any(p == prefix / "act_conf.json" for _, p in selected):
        raise ValueError("ZIP role has no act_conf.json")
    if not any(len(p.relative_to(prefix).parts) == 2 and
               p.relative_to(prefix).parts[0] == "action" and
               p.suffix.lower() == ".png"
               for _, p in selected if p == prefix or prefix in p.parents):
        raise ValueError("ZIP role has no action PNG frames")
    return selected, prefix


def validate_native_role(folder: Path):
    """Check the fields the actual DyberPet animation loader consumes."""
    try:
        pet = json.loads((folder / "pet_conf.json").read_text(encoding="utf-8"))
        actions = json.loads((folder / "act_conf.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid DyberPet configuration JSON") from exc
    if not isinstance(pet, dict) or not isinstance(actions, dict) or not actions:
        raise ValueError("Role configuration must contain action objects")
    for required in ("default", "drag", "fall"):
        if not isinstance(pet.get(required), str):
            raise ValueError("Missing required action binding: " + required)
    for label, value in actions.items():
        if not isinstance(label, str) or not isinstance(value, dict):
            raise ValueError("Invalid action definition")
        prefix = value.get("images")
        if not isinstance(prefix, str) or not re.fullmatch(r"[\w-]+", prefix):
            raise ValueError("Invalid image prefix in action: " + label)
        files = list((folder / "action").glob(prefix + "_*.png"))
        indexes = []
        for f in files:
            match = re.fullmatch(re.escape(prefix) + r"_(\d+)\.png", f.name)
            if match:
                indexes.append(int(match.group(1)))
        if not indexes:
            raise ValueError("Missing PNG animation: " + label)
        if len(set(indexes)) != len(indexes):
            raise ValueError("Duplicate numbered animation frames: " + label)
        if set(indexes) != set(range(min(indexes), max(indexes) + 1)):
            raise ValueError("Animation has numbered frame gaps: " + label)
        try:
            refresh = float(value.get("frame_refresh", 0.5))
        except (ValueError, TypeError):
            raise ValueError("Invalid animation frame rate: " + label)
        if not (0.015 <= refresh <= 10):
            raise ValueError("Unsafe animation frame rate: " + label)
    referenced = []
    for key in ("default", "up", "down", "left", "right", "drag", "fall",
                "prefall", "on_floor", "focus"):
        if key in pet and pet[key] is not None:
            referenced.append(pet[key])
    pats = pet.get("patpat")
    if isinstance(pats, str):
        referenced.append(pats)
    elif isinstance(pats, dict):
        referenced += list(pats.values())
    for row in pet.get("random_act", []):
        referenced.extend(row.get("act_list", []))
    for row in pet.get("accessory_act", []):
        referenced.extend(row.get("act_list", []))
        referenced.extend(row.get("acc_list", []))
    unknown = sorted({str(name) for name in referenced if name not in actions})
    if unknown:
        raise ValueError("Undefined action references: " + ", ".join(unknown))
    return {"actions": len(actions),
            "images": sum(len(list((folder / "action").glob(
                config["images"] + "_*.png"))) for config in actions.values())}


def install_native_role(archive_path: Path, output_root: Path, *,
                        role_folder: str | None = None) -> Path:
    archive_path = archive_path.expanduser().resolve()
    output_root = output_root.expanduser().resolve()
    if not archive_path.is_file() or archive_path.suffix.lower() != ".zip":
        raise ValueError("Please supply a local .zip character archive")
    with zipfile.ZipFile(archive_path) as archive:
        members, prefix = inspect_zip(archive)
        suggested = role_folder or (
            str(prefix.name) if str(prefix) != "." else archive_path.stem
        )
        if role_folder is not None and not re.fullmatch(
                r"[A-Za-z][A-Za-z0-9_-]{0,39}", role_folder):
            raise ValueError("Explicit role folder must contain safe ASCII characters")
        destination_name = (role_folder if role_folder is not None else
                            available_role_folder(output_root, suggested))
        destination = output_root / destination_name
        if destination.exists():
            raise FileExistsError("Character folder already exists: " + str(destination))
        output_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=output_root,
                                         prefix=".native-role-install-") as temp:
            staged = Path(temp) / destination_name
            staged.mkdir()
            for member, path in members:
                if prefix != PurePosixPath(".") and prefix not in path.parents:
                    continue
                relative = path.relative_to(prefix)
                if str(relative) == ".":
                    continue
                target = staged.joinpath(*relative.parts)
                if not target.resolve().is_relative_to(staged.resolve()):
                    raise ValueError("Archive tries to escape the role directory")
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member) as source, target.open("wb") as out:
                    shutil.copyfileobj(source, out, length=1024 * 1024)
            check = validate_native_role(staged)
            (staged / "INSTALL_REPORT.json").write_text(
                json.dumps({"archive": archive_path.name,
                            "safe_extraction": True,
                            "validation": check,
                            "art_license": "Unverified; read artist's original terms"},
                           ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8")
            # Rename within same filesystem. Recheck collision in case a role
            # appeared while the archive was being processed.
            if destination.exists():
                raise FileExistsError("Character folder now exists: " + str(destination))
            staged.rename(destination)
    return destination



def inspect_native_folder(source: Path):
    """Read-only guard for an extracted, single legacy main-role folder.

    This is intentionally *not* a full downloaded application root; the
    user must select its res/role/<name> directory, not the app EXE or res/pet.
    """
    source = Path(source).expanduser()
    if source.is_symlink() or not source.is_dir():
        raise ValueError("Select a real, unlinked DyberPet role folder")
    source = source.resolve()
    if not (source / "pet_conf.json").is_file() or not (
            source / "act_conf.json").is_file():
        raise ValueError("Select res/role/<name>, not an entire old application")
    if len(source.parts) >= 2 and source.parent.name.lower() == "pet" and (
            source.parent.parent.name.lower() == "res"):
        raise ValueError("res/pet contains mini-pets; select a res/role main character")
    files, total = [], 0
    for entry in sorted(source.rglob("*")):
        if entry.is_symlink():
            raise ValueError("Linked character resource not permitted")
        if entry.is_dir():
            continue
        if not entry.is_file():
            raise ValueError("Special character resource not permitted")
        if entry.suffix.lower() in BLOCKED_SUFFIXES:
            raise ValueError("Executable/script in role folder: " + entry.name)
        size = entry.stat().st_size
        if size > MAX_SINGLE_FILE:
            raise ValueError("Role file exceeds 64 MiB limit")
        total += size
        files.append(entry)
        if len(files) > MAX_FILES or total > MAX_TOTAL_SIZE:
            raise ValueError("Role folder exceeds safe limits")
    check = validate_native_role(source)
    return {"source": source, "files": files, "total_bytes": total,
            "validation": check}


def install_native_folder(source_folder: Path, output_root: Path, *,
                          role_folder: str | None = None) -> Path:
    """Stage a previously extracted original role without overwriting anything."""
    source = Path(source_folder).expanduser()
    inventory = inspect_native_folder(source)
    source = inventory["source"]
    output_root = Path(output_root).expanduser().resolve()
    if output_root == source or output_root.is_relative_to(source):
        raise ValueError("Output root must be outside original role folder")
    if role_folder is not None and not re.fullmatch(
            r"[A-Za-z][A-Za-z0-9_-]{0,39}", role_folder):
        raise ValueError("Explicit role folder must be safe ASCII")
    name = (role_folder if role_folder is not None else
            available_role_folder(output_root, source.name))
    destination = output_root / name
    if destination.exists() or destination.is_symlink():
        raise FileExistsError("Character folder already exists: " + str(destination))
    output_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output_root,
                                     prefix=".native-folder-install-") as tmp:
        staged = Path(tmp) / name
        staged.mkdir()
        for file in inventory["files"]:
            # Re-check links in case the external folder is modified.
            if file.is_symlink() or not file.is_file():
                raise ValueError("Source changed during local installation")
            dst = staged / file.relative_to(source)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(file, dst)
        validation = validate_native_role(staged)
        (staged / "INSTALL_REPORT.json").write_text(json.dumps({
            "source_kind": "extracted_native_role_folder",
            "safe_extraction": True, "validation": validation,
            "source_files": len(inventory["files"]),
            "art_license": "Unverified; original artist's permissions still required",
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if destination.exists() or destination.is_symlink():
            raise FileExistsError("Character folder appeared during install")
        staged.rename(destination)
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path, help="Local DyberPet role .zip")
    parser.add_argument("--output-root", type=Path,
                        default=Path(__file__).resolve().parents[1] / "res" / "role")
    parser.add_argument("--folder", help="Custom ASCII output folder (never overwrite)")
    args = parser.parse_args()
    try:
        role = install_native_role(args.archive, args.output_root,
                                   role_folder=args.folder)
    except (ValueError, OSError, zipfile.BadZipFile, RuntimeError) as exc:
        parser.exit(1, f"Install failed: {exc}\n")
    print("Installed:", role)
    print("Restart DyberPet and choose the role in 系统 → 角色管理")


if __name__ == "__main__":
    raise SystemExit(main())

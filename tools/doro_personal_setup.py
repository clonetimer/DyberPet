"""One-click PERSONAL local Doro ZIP setup. Never contacts a server or ships artwork.

The user obtains the original archive themselves from the creator's download
page. DyberPet detects it in Downloads and privately installs just the model
tree into the current Windows user's writable application data directory.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import tempfile
import zipfile

from tools.doro_live2d_local import inspect_local_live2d

MAX_ZIP_BYTES = 350 * 1024 * 1024
MAX_MEMBER_BYTES = 100 * 1024 * 1024
MAX_TOTAL_BYTES = 350 * 1024 * 1024
MAX_MEMBERS = 600
PERMITTED_EXTENSIONS = (
    ".json", ".moc3", ".png", ".jpeg", ".jpg", ".webp",
    ".wav", ".mp3", ".ogg", ".txt", ".md",
)
WINDOWS_RESERVED = {"CON", "PRN", "AUX", "NUL", *("COM" + str(i) for i in range(1, 10)),
                    *("LPT" + str(i) for i in range(1, 10))}


def _safe_parts(name):
    if not isinstance(name, str) or not name or "\\" in name or "\x00" in name:
        raise ValueError("Archive has an unsafe Windows filename")
    raw = name.rstrip("/")
    path = PurePosixPath(raw)
    parts = path.parts
    if (path.is_absolute() or len(parts) > 12 or not parts
            or any(p in ("", ".", "..") for p in parts)
            or any(":" in p or p.endswith((" ", ".")) for p in parts)
            or any(p.split(".")[0].upper() in WINDOWS_RESERVED for p in parts)):
        raise ValueError("Archive path may not escape the local model directory")
    return parts


def find_doro_archives(downloads):
    """No network and no broad filesystem sweep, just user's Downloads folder."""
    directory = Path(downloads).expanduser()
    if not directory.is_dir():
        return []
    found = []
    for entry in directory.iterdir():
        if (entry.is_file() and not entry.is_symlink()
                and entry.suffix.casefold() == ".zip"
                and ("doro" in entry.name.casefold()
                     or "0x4682b4" in entry.name.casefold())
                and entry.stat().st_size <= MAX_ZIP_BYTES):
            found.append(entry)
    return sorted(found, key=lambda p: p.stat().st_mtime, reverse=True)


def find_doro_archives_in_directories(directories):
    """Merge likely Windows Downloads locations without searching other files."""
    ordered = []
    known = set()
    for folder in directories:
        if not folder:
            continue
        path = Path(folder).expanduser()
        canonical = str(path).casefold()
        if canonical in known:
            continue
        known.add(canonical)
        ordered.extend(find_doro_archives(path))
    return sorted(set(ordered), key=lambda p: p.stat().st_mtime, reverse=True)


def _candidate_manifest(zf):
    infos = zf.infolist()
    if len(infos) > MAX_MEMBERS:
        raise ValueError("Archive contains too many files")
    available = {}
    total_bytes = 0
    for info in infos:
        parts = _safe_parts(info.filename)
        if info.is_dir():
            continue
        if stat.S_ISLNK(info.external_attr >> 16):
            raise ValueError("Archive contains a linked resource")
        if info.file_size > MAX_MEMBER_BYTES:
            raise ValueError("Archive has a resource exceeding safe limits")
        total_bytes += info.file_size
        if total_bytes > MAX_TOTAL_BYTES:
            raise ValueError("Archive is too large to unpack safely")
        key = "/".join(parts).casefold()
        if key in available:
            raise ValueError("Archive contains a duplicate/case-conflicting file")
        available[key] = (info, parts)
    models = [
        (info, parts) for info, parts in available.values()
        if parts[-1].casefold().endswith(".model3.json")
        and "doro" in "/".join(parts).casefold()
    ]
    if len(models) != 1:
        raise ValueError("Expected exactly one Dororong Doro .model3.json in the downloaded ZIP")
    model_info, model_parts = models[0]
    model_dir = model_parts[:-1]
    relevant = [
        (info, parts) for info, parts in available.values()
        if parts[:len(model_dir)] == model_dir and len(parts) > len(model_dir)
    ]
    if not relevant or len(relevant) > MAX_MEMBERS:
        raise ValueError("No local Dororong model resources found")
    for info, parts in relevant:
        if not parts[-1].lower().endswith(PERMITTED_EXTENSIONS):
            raise ValueError("Unexpected active/non-model file in Doro archive")
    # Require the exact creator model manifest to be parseable before writing.
    raw = zf.read(model_info)
    try:
        manifest = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeError, ValueError) as exc:
        raise ValueError("Invalid downloaded Doro model JSON") from exc
    if not isinstance(manifest, dict) or "FileReferences" not in manifest:
        raise ValueError("Downloaded ZIP does not declare a Cubism model")
    return model_parts, relevant


def setup_personal_doro_zip(zip_path, private_root):
    """Unpack to app-local private cache, preserving source art byte-for-byte.

    Returns a model3.json Path. No upload, network request, image generation,
    source art modification, or copying into a git repository / release ZIP.
    """
    archive = Path(zip_path).expanduser()
    if (archive.is_symlink() or not archive.is_file()
            or archive.suffix.casefold() != ".zip"
            or archive.stat().st_size > MAX_ZIP_BYTES):
        raise ValueError("Select your original downloaded Doro .zip file")
    root = Path(private_root).expanduser()
    root.mkdir(parents=True, exist_ok=True)
    if root.is_symlink():
        raise ValueError("Private asset destination must not be a symlink")
    hash_value = hashlib.sha256()
    with archive.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hash_value.update(chunk)
    target = root / ("Doro_personal_" + hash_value.hexdigest()[:16])
    with zipfile.ZipFile(archive) as zf:
        model_parts, entries = _candidate_manifest(zf)
        expected_model = target / model_parts[-1]
        if expected_model.is_file():
            inspect_local_live2d(expected_model)
            return expected_model
        if target.exists():
            raise ValueError("An incomplete personal Doro extraction exists; please remove it")
        # Create under the same parent for an atomic final directory rename.
        with tempfile.TemporaryDirectory(prefix=".doro-staging-", dir=root) as tmp:
            stage = Path(tmp)
            for info, parts in entries:
                rel = parts[len(model_parts) - 1:]
                output = stage.joinpath(*rel)
                output.parent.mkdir(parents=True, exist_ok=True)
                if not output.resolve().is_relative_to(stage.resolve()):
                    raise ValueError("Unsafe ZIP entry")
                with zf.open(info) as source, output.open("wb") as dest:
                    copied = shutil.copyfileobj(source, dest, length=1024 * 1024)
                if output.stat().st_size != info.file_size:
                    raise ValueError("Incomplete Doro source resource")
            extracted_model = stage / model_parts[-1]
            inspect_local_live2d(extracted_model)
            stage.rename(target)
    return expected_model

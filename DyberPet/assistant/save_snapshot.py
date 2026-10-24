"""Verified portable backups of DyberPet on-disk settings and save data.

Deliberately excludes character art, voice and AI model assets. No restore
operation is performed inside a running DyberPet process.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import tempfile
from zipfile import ZipFile, ZIP_DEFLATED, BadZipFile

FILES = ("settings.json", "pet_data.json", "task_data.json", "act_data.json", "version")
REQUIRED = {"settings.json", "pet_data.json"}
FILE_LIMIT = 64 * 1024 * 1024
TOTAL_LIMIT = 128 * 1024 * 1024
MANIFEST_LIMIT = 64 * 1024


class BackupError(ValueError):
    pass


def _digest(stream):
    h = hashlib.sha256()
    total = 0
    for block in iter(lambda: stream.read(1024 * 1024), b""):
        total += len(block)
        if total > FILE_LIMIT:
            raise BackupError("Data file exceeds backup safety limit")
        h.update(block)
    return total, h.hexdigest()


def verify_backup(path):
    """Strict, read-only membership and SHA256 verification of backup ZIP."""
    try:
        with ZipFile(path) as archive:
            infos = archive.infolist()
            names = [x.filename for x in infos]
            if len(names) != len(set(names)) or "manifest.json" not in names:
                raise BackupError("Missing manifest or duplicate archive member")
            if len(names) > len(FILES) + 1:
                raise BackupError("Unexpected number of archive members")
            for item in infos:
                if item.is_dir() or stat.S_ISLNK(item.external_attr >> 16):
                    raise BackupError("Archives containing links or folders are not allowed")
                limit = MANIFEST_LIMIT if item.filename == "manifest.json" else FILE_LIMIT
                if item.file_size > limit:
                    raise BackupError("Oversized backup member")
            manifest_bytes = archive.read("manifest.json")
            if len(manifest_bytes) > MANIFEST_LIMIT:
                raise BackupError("Oversized backup manifest")
            manifest = json.loads(manifest_bytes)
            if not isinstance(manifest, dict) or manifest.get("format") != "dyberpet-data-v1":
                raise BackupError("Unsupported backup version")
            files = manifest.get("files")
            if not isinstance(files, list) or not files or len(files) > len(FILES):
                raise BackupError("Invalid file manifest")
            identifiers = [row.get("name") for row in files if isinstance(row, dict)]
            if len(identifiers) != len(files) or len(set(identifiers)) != len(identifiers):
                raise BackupError("Invalid manifest entries")
            if not REQUIRED.issubset(identifiers) or set(identifiers) - set(FILES):
                raise BackupError("Missing essential files or unknown manifest file")
            if set(names) != {"manifest.json"} | {"data/" + name for name in identifiers}:
                raise BackupError("Archive paths do not match manifest")
            total = 0
            for row in files:
                if type(row.get("size")) is not int or row["size"] < 0:
                    raise BackupError("Invalid entry size")
                if not isinstance(row.get("sha256"), str) or len(row["sha256"]) != 64:
                    raise BackupError("Invalid entry checksum")
                with archive.open("data/" + row["name"]) as member:
                    size, digest = _digest(member)
                total += size
                if total > TOTAL_LIMIT or size != row["size"] or digest != row["sha256"]:
                    raise BackupError("Backup content failed integrity check")
            return {"ok": True, "files": identifiers, "total_bytes": total}
    except (OSError, BadZipFile, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise BackupError("Invalid or unreadable DyberPet backup") from exc


def create_backup(data_dir, destination):
    """Write and verify a ZIP, then publish without overwriting an existing file."""
    root = Path(data_dir).expanduser().resolve()
    dest = Path(destination).expanduser().absolute()
    if not root.is_dir() or not dest.parent.is_dir():
        raise BackupError("Data folder or destination folder does not exist")
    if dest.exists() or dest.is_symlink():
        raise FileExistsError("The chosen backup file already exists")
    sources = []
    total = 0
    for name in FILES:
        path = root / name
        if path.is_symlink():
            raise BackupError("Symbolic-link saves cannot be backed up")
        if not path.exists():
            if name in REQUIRED:
                raise BackupError("Missing essential user save: " + name)
            continue
        if not path.is_file() or path.stat().st_size > FILE_LIMIT:
            raise BackupError("Invalid or oversized user save: " + name)
        total += path.stat().st_size
        if total > TOTAL_LIMIT:
            raise BackupError("Total user save size exceeds backup limit")
        sources.append((name, path))
    descriptor, temp = tempfile.mkstemp(prefix=".dyberpet-backup-", dir=str(dest.parent))
    os.close(descriptor)
    try:
        rows = []
        with ZipFile(temp, "w", compression=ZIP_DEFLATED, compresslevel=6) as archive:
            for name, path in sources:
                archive.write(path, "data/" + name)
                with archive.open("data/" + name) as member:
                    size, checksum = _digest(member)
                rows.append({"name": name, "size": size, "sha256": checksum})
            archive.writestr("manifest.json", json.dumps({
                "format": "dyberpet-data-v1",
                "scope": "data files only; excludes character art, audio and models",
                "files": rows,
            }, ensure_ascii=False))
        verify_backup(temp)
        created = False
        try:
            with open(dest, "xb") as output:
                created = True
                with open(temp, "rb") as source:
                    shutil.copyfileobj(source, output, 1024 * 1024)
                output.flush()
                os.fsync(output.fileno())
            return verify_backup(dest)
        except Exception:
            # A competing writer can win the exclusive-create race.
            if created:
                dest.unlink(missing_ok=True)
            raise
    finally:
        Path(temp).unlink(missing_ok=True)

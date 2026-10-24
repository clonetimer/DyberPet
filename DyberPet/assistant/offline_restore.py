"""Offline restore with SHA-256, schema guards, rollback and crash journal.

Call only when the desktop application's single-instance lock is held by the
restoration process. Never invoke from a running pet GUI. No third-party assets.
"""
from __future__ import annotations

import json
import os
import shutil
import stat
import uuid
from pathlib import Path
from zipfile import ZipFile

from .save_snapshot import BackupError, REQUIRED, FILES, FILE_LIMIT, create_backup, verify_backup

JOURNAL = ".dyberpet-restore-pending.json"
PREFIX = ".dyberpet-pre-restore-"
STAGE_PREFIX = ".dyberpet-restore-stage-"


def data_directory():
    """Match settings.CONFIGDIR/data without importing Qt or initializing saves."""
    import sys
    if sys.platform == "linux":
        return Path(os.environ["HOME"]) / ".config" / "DyberPet" / "data"
    return Path.cwd() / "data"


def _validate_names(data):
    if not isinstance(data, dict):
        raise BackupError("Restore JSON must be a top-level object")


def _check_content(folder):
    for name in FILES:
        path = folder / name
        if not path.exists():
            if name in REQUIRED:
                raise BackupError("Required restored file missing: " + name)
            continue
        if path.is_symlink() or not path.is_file() or path.stat().st_size > FILE_LIMIT:
            raise BackupError("Invalid restored data file: " + name)
        if name == "version":
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, UnicodeError) as exc:
            raise BackupError("Invalid JSON in restored file: " + name) from exc
        _validate_names(payload)
        if name == "pet_data.json":
            if not payload or not any(
                isinstance(value, dict) and
                {"HP", "HP_tier", "FV", "FV_lvl"}.issubset(value)
                for value in payload.values()
            ):
                raise BackupError("Restored pet data has no compatible pet entry")
        if name == "settings.json":
            value = payload.get("default_pet")
            if value is not None and not isinstance(value, str):
                raise BackupError("Invalid default_pet in restored settings")


def _safe_transaction_paths(data_dir):
    data = Path(data_dir).expanduser().absolute()
    if data.name != "data":
        raise BackupError("Restore target must be the DyberPet data directory")
    if data.is_symlink() or data.parent.is_symlink():
        raise BackupError("Cannot restore through a symbolic link")
    if not data.parent.is_dir():
        raise BackupError("Restore target parent does not exist")
    return data, data.parent / JOURNAL


def recover_interrupted_restore(data_dir):
    """Fix only an interrupted directory rename; never overwrite live data."""
    # An untouched first installation does not have a config directory yet.
    parent = Path(data_dir).expanduser().absolute().parent
    if not parent.exists():
        return "none"
    data, journal = _safe_transaction_paths(data_dir)
    if not journal.exists() and not journal.is_symlink():
        return "none"
    if journal.is_symlink() or not journal.is_file() or journal.stat().st_size > 4096:
        raise BackupError("Unsafe restore journal; manual assistance required")
    try:
        state = json.loads(journal.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise BackupError("Corrupted restore journal; preserve files for recovery") from exc
    previous = state.get("previous") if isinstance(state, dict) else None
    stage = state.get("stage") if isinstance(state, dict) else None
    if (not isinstance(state, dict) or
            state.get("format") != "dyberpet-offline-restore-v1" or
            not isinstance(previous, str) or not isinstance(stage, str) or
            not previous.startswith(PREFIX) or not stage.startswith(STAGE_PREFIX) or
            len(previous) != len(PREFIX) + 32 or len(stage) != len(STAGE_PREFIX) + 32 or
            any(c not in "0123456789abcdef" for c in previous[len(PREFIX):]) or
            any(c not in "0123456789abcdef" for c in stage[len(STAGE_PREFIX):])):
        raise BackupError("Unknown restore journal; automatic recovery refused")
    old_dir = data.parent / previous
    stage_dir = data.parent / stage
    if old_dir.is_symlink() or stage_dir.is_symlink():
        raise BackupError("Unsafe recovery target")
    if data.exists():
        # Transaction completed or never started; preserve old/backup in place.
        journal.unlink()
        return "already-has-data"
    if not old_dir.is_dir():
        raise BackupError("Original data absent; automatic recovery refused")
    old_dir.rename(data)
    journal.unlink()
    return "rolled-back-interrupted-restore"


def restore_backup(archive_path, data_dir, *, failure_hook=None):
    """Offline transactional data-directory switch, retaining two recovery copies.

    failure_hook is only for simulating a commit-step failure in regression tests.
    """
    data, journal = _safe_transaction_paths(data_dir)
    supplied = Path(archive_path).expanduser()
    if supplied.is_symlink():
        raise BackupError("Backup archive must not be a symbolic link")
    source = supplied.resolve()
    if not source.is_file() or data in source.parents:
        raise BackupError("Archive must be a regular file outside active saves")
    if journal.exists() or journal.is_symlink():
        raise BackupError("Pending interrupted restore: recover it first")
    if not data.is_dir():
        raise BackupError("Existing data directory required; launch DyberPet once first")
    if data.is_symlink() or not (data / "settings.json").is_file() or not (data / "pet_data.json").is_file():
        raise BackupError("Current saves are incomplete or unsafe")
    report = verify_backup(source)
    ident = uuid.uuid4().hex
    stage = data.parent / (STAGE_PREFIX + ident)
    previous = data.parent / (PREFIX + ident)
    pre_zip = data.parent / (PREFIX + ident + ".zip")
    if any(p.exists() or p.is_symlink() for p in (stage, previous, pre_zip)):
        raise BackupError("Unexpected restore transaction path already exists")
    stage.mkdir(mode=0o700)
    wrote_journal = False
    moved_old = False
    switched = False
    try:
        with ZipFile(source) as archive:
            for name in report["files"]:
                destination = stage / name
                with archive.open("data/" + name) as reader, destination.open("xb") as writer:
                    shutil.copyfileobj(reader, writer, 1024 * 1024)
        _check_content(stage)
        # Preserve an independent, checksum-verified old-state ZIP before
        # renaming anything. Missing current data blocks the transaction.
        create_backup(data, pre_zip)
        record = json.dumps({
            "format": "dyberpet-offline-restore-v1",
            "previous": previous.name, "stage": stage.name,
        }, separators=(",", ":")).encode("utf-8")
        fd = os.open(str(journal), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        wrote_journal = True
        with os.fdopen(fd, "wb") as stream:
            stream.write(record)
            stream.flush()
            os.fsync(stream.fileno())
        data.rename(previous)
        moved_old = True
        if failure_hook is not None:
            failure_hook()
        stage.rename(data)
        switched = True
        journal.unlink()
        wrote_journal = False
        return {
            "ok": True, "restored": report["files"],
            "pre_restore_archive": str(pre_zip),
            "pre_restore_directory": str(previous),
        }
    except Exception:
        # In-process failure: restore old data before surfacing any error.
        if moved_old and not switched and not data.exists() and previous.exists():
            previous.rename(data)
            moved_old = False
        if wrote_journal and data.exists():
            journal.unlink()
        raise
    finally:
        if stage.is_dir() and not stage.is_symlink():
            shutil.rmtree(stage)

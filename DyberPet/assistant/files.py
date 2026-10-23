"""Small, reversible file tool for the desktop pet's explicitly owned workspace.

No generic filesystem agent. The character/model cannot choose arbitrary
paths or execute tool calls: the human selects the GUI file action. All writes
are restricted to a dedicated folder controlled by the pet application.
"""
from __future__ import annotations

import os
import re
import secrets
from pathlib import Path

_ALLOWED = {".txt", ".md", ".json", ".csv"}
_MAX_BYTES = 256 * 1024
_INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_WINDOWS_DEVICES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


class WorkspaceError(ValueError):
    pass


class PetWorkspace:
    def __init__(self, root: Path):
        requested_root = Path(root).expanduser()
        if requested_root.is_symlink():
            raise WorkspaceError("Workspace root must not be a symlink")
        self.root = requested_root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.trash = self.root / ".pet_trash"
        if self.trash.is_symlink():
            raise WorkspaceError("Trash folder must not be a symlink")
        self.trash.mkdir(exist_ok=True)

    @staticmethod
    def validate_name(name: str) -> str:
        name = str(name).strip()
        if (not name or name in (".", "..") or len(name) > 120
                or _INVALID.search(name) or name.endswith((" ", "."))
                or Path(name).name != name):
            raise WorkspaceError("Invalid file name; please enter a single file name")
        if name.split(".", 1)[0].upper() in _WINDOWS_DEVICES:
            raise WorkspaceError("Reserved Windows file name")
        if Path(name).suffix.lower() not in _ALLOWED:
            raise WorkspaceError("Only .txt/.md/.json/.csv files are supported")
        if name.startswith("."):
            raise WorkspaceError("Hidden files cannot be managed")
        return name

    def _file(self, name: str) -> Path:
        path = self.root / self.validate_name(name)
        if path.is_symlink():
            raise WorkspaceError("Symbolic links are not managed")
        return path

    def list_files(self) -> list[str]:
        return sorted(
            path.name for path in self.root.iterdir()
            if path.is_file() and not path.is_symlink()
            and not path.name.startswith(".")
            and path.suffix.lower() in _ALLOWED
        )

    def create(self, name: str, content: str = "") -> Path:
        path = self._file(name)
        payload = content.encode("utf-8")
        if len(payload) > _MAX_BYTES:
            raise WorkspaceError("File content exceeds 256 KiB")
        try:
            descriptor = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError as exc:
            raise WorkspaceError("This file already exists; overwrite is disabled") from exc
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(payload)
        except Exception:
            path.unlink(missing_ok=True)
            raise
        return path

    def soft_delete(self, name: str) -> str:
        """Move only one regular workspace file to the recoverable app trash."""
        path = self._file(name)
        if not path.is_file():
            raise WorkspaceError("File not found in assistant workspace")
        key = secrets.token_hex(12) + "__" + path.name
        destination = self.trash / key
        # Use the same filesystem; never modify a path outside this workspace.
        path.rename(destination)
        return key

    def deleted_files(self) -> list[str]:
        return sorted(path.name for path in self.trash.iterdir()
                      if path.is_file() and not path.is_symlink()
                      and "__" in path.name)

    def restore(self, trash_key: str) -> Path:
        if (not isinstance(trash_key, str) or len(trash_key) < 27 or
                not re.fullmatch(r"[0-9a-f]{24}__.+", trash_key)):
            raise WorkspaceError("Invalid recycle record")
        source = self.trash / trash_key
        if not source.is_file() or source.is_symlink():
            raise WorkspaceError("Recycle record does not exist")
        name = trash_key.split("__", 1)[1]
        dest = self._file(name)
        if dest.exists():
            raise WorkspaceError("Cannot restore: target already exists")
        source.rename(dest)
        return dest

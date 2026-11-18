"""Explicit approval-gated local actions for the DyberPet assistant.

The model cannot call this runtime. UI handlers prepare a bounded action,
show its exact preview, obtain an affirmative human decision, and only then
consume a short-lived approval to execute it inside PetWorkspace.
"""
from __future__ import annotations

import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Optional

from .files import PetWorkspace, WorkspaceError
from .preferences import default_preference_path

APPROVAL_TTL_SECONDS = 60
MAX_AUDIT_ROWS = 2000
MAX_ACTION_CONTENT = 256 * 1024


class ActionDenied(RuntimeError):
    pass


class ActionRuntime:
    """Small allow-list executor with one-shot approvals and local audit."""

    ALLOWED_ACTIONS = frozenset(("create_file", "create_note", "trash_file", "restore_file"))

    def __init__(self, workspace: PetWorkspace, audit_path: Optional[Path] = None,
                 *, approval_ttl: int = APPROVAL_TTL_SECONDS):
        self.workspace = workspace
        if type(approval_ttl) is not int or not 1 <= approval_ttl <= 300:
            raise ValueError("approval TTL must be 1–300 seconds")
        self.approval_ttl = approval_ttl
        self.audit_path = Path(audit_path) if audit_path else (
            default_preference_path().parent / "assistant-actions.sqlite3")
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)
        if self.audit_path.is_symlink():
            raise ValueError("Action audit database cannot be a symlink")
        self._pending: Dict[str, dict] = {}
        self._lock = threading.RLock()
        self._initialize()

    @contextmanager
    def _connect(self):
        if self.audit_path.is_symlink():
            raise ValueError("Action audit database cannot be a symlink")
        db = sqlite3.connect(str(self.audit_path), timeout=5)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=5000")
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def _initialize(self):
        with self._connect() as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS action_audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    target TEXT NOT NULL,
                    status TEXT NOT NULL,
                    detail TEXT NOT NULL,
                    created_at REAL NOT NULL
                )
            """)
            db.execute("""
                CREATE INDEX IF NOT EXISTS idx_action_audit_created
                ON action_audit(created_at DESC)
            """)

    def set_workspace(self, workspace: PetWorkspace):
        if not isinstance(workspace, PetWorkspace):
            raise TypeError("workspace must be a PetWorkspace")
        with self._lock:
            self._pending.clear()
            self.workspace = workspace

    def _record(self, request_id: str, action: str, target: str,
                status: str, detail: str = ""):
        with self._connect() as db:
            db.execute(
                "INSERT INTO action_audit(request_id,action,target,status,detail,created_at) "
                "VALUES(?,?,?,?,?,?)",
                (request_id, action, target[:512], status, detail[:1000], time.time()),
            )
            db.execute("""
                DELETE FROM action_audit WHERE id NOT IN (
                    SELECT id FROM action_audit ORDER BY id DESC LIMIT ?
                )
            """, (MAX_AUDIT_ROWS,))

    def prepare(self, action: str, arguments: dict) -> dict:
        if action not in self.ALLOWED_ACTIONS:
            raise ActionDenied("Action is not registered in the local allow-list")
        if not isinstance(arguments, dict):
            raise ActionDenied("Action arguments must be an object")
        args = dict(arguments)
        target = ""
        if action in ("create_file", "create_note"):
            name = self.workspace.validate_name(args.get("name", ""))
            content = args.get("content", "")
            if not isinstance(content, str):
                raise ActionDenied("File content must be text")
            if len(content.encode("utf-8")) > MAX_ACTION_CONTENT:
                raise ActionDenied("File content exceeds 256 KiB")
            suffix = Path(name).suffix.lower()
            if action == "create_note" and suffix not in (".md", ".txt"):
                raise ActionDenied("Notes must use .md or .txt")
            if (self.workspace.root / name).exists():
                raise ActionDenied("Target already exists; overwrite is disabled")
            args = {"name": name, "content": content}
            target = str(self.workspace.root / name)
            preview = "Create new file (no overwrite): " + target
        elif action == "trash_file":
            name = self.workspace.validate_name(args.get("name", ""))
            path = self.workspace.root / name
            if path.is_symlink() or not path.is_file():
                raise ActionDenied("Only an existing regular workspace file can be moved")
            args = {"name": name}
            target = str(path)
            preview = "Move to recoverable workspace trash: " + target
        else:
            key = args.get("key", "")
            if not isinstance(key, str) or key not in self.workspace.deleted_files():
                raise ActionDenied("Restore key is not present in the workspace trash")
            name = key.split("__", 1)[1]
            if (self.workspace.root / name).exists():
                raise ActionDenied("Restore target already exists; overwrite is disabled")
            args = {"key": key}
            target = str(self.workspace.root / name)
            preview = "Restore workspace file to: " + target

        request_id = uuid.uuid4().hex
        created = time.monotonic()
        with self._lock:
            expired = [key for key, value in self._pending.items()
                       if created - value["created"] > self.approval_ttl]
            for key in expired:
                self._pending.pop(key, None)
            if len(self._pending) >= 128:
                raise ActionDenied("Too many pending actions; finish or cancel an existing request")
            self._pending[request_id] = {
                "action": action, "arguments": args, "target": target,
                "created": created, "approved": False,
            }
        try:
            self._record(request_id, action, target, "prepared", "Awaiting explicit user approval")
        except Exception:
            with self._lock:
                self._pending.pop(request_id, None)
            raise
        return {
            "request_id": request_id, "action": action, "preview": preview,
            "approval_required": True, "expires_in_seconds": self.approval_ttl,
        }

    def approve(self, request_id: str, confirmed: bool) -> bool:
        with self._lock:
            pending = self._pending.get(request_id)
            if pending is None:
                raise ActionDenied("Action request is missing, expired or already consumed")
            if time.monotonic() - pending["created"] > self.approval_ttl:
                self._pending.pop(request_id, None)
                self._record(request_id, pending["action"], pending["target"],
                             "expired", "Approval window elapsed")
                raise ActionDenied("Action approval expired; prepare it again")
            if confirmed is not True:
                self._pending.pop(request_id, None)
                self._record(request_id, pending["action"], pending["target"],
                             "denied", "User declined the action")
                return False
            pending["approved"] = True
            pending["approved_at"] = time.monotonic()
            self._record(request_id, pending["action"], pending["target"],
                         "approved", "Explicit UI confirmation")
            return True

    def execute(self, request_id: str) -> dict:
        with self._lock:
            pending = self._pending.get(request_id)
            if pending is None:
                raise ActionDenied("Action request is missing, expired or already consumed")
            if not pending["approved"]:
                raise ActionDenied("Action has not been approved by the user")
            if time.monotonic() - pending["approved_at"] > self.approval_ttl:
                self._pending.pop(request_id, None)
                self._record(request_id, pending["action"], pending["target"],
                             "expired", "Approval expired before execution")
                raise ActionDenied("Action approval expired; prepare it again")
            self._pending.pop(request_id, None)

        action, args = pending["action"], pending["arguments"]
        try:
            if action in ("create_file", "create_note"):
                result = self.workspace.create(args["name"], args["content"])
                value = {"path": str(result), "name": result.name}
            elif action == "trash_file":
                key = self.workspace.soft_delete(args["name"])
                value = {"trash_key": key, "name": args["name"]}
            elif action == "restore_file":
                result = self.workspace.restore(args["key"])
                value = {"path": str(result), "name": result.name}
            else:  # Defensive even though prepare is allow-listed.
                raise ActionDenied("Action is not registered")
        except Exception as exc:
            self._record(request_id, action, pending["target"], "failed", str(exc))
            raise
        audit_warning = ""
        try:
            self._record(request_id, action, pending["target"], "executed", "Completed successfully")
        except Exception as exc:
            # The file action has already completed. Never report it as failed
            # or invite a duplicate retry just because the audit volume failed.
            audit_warning = "Action completed but audit write failed: " + str(exc)[:300]
        return {
            "request_id": request_id, "action": action, "result": value,
            "audit_warning": audit_warning,
        }

    def audit_log(self, *, limit: int = 100) -> list[dict]:
        if type(limit) is not int or not 1 <= limit <= 500:
            raise ValueError("audit limit must be 1–500")
        with self._connect() as db:
            rows = db.execute(
                "SELECT request_id,action,target,status,detail,created_at "
                "FROM action_audit ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(row) for row in rows]

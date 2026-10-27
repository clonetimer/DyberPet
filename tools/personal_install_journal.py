"""Crash-tolerant LOCAL per-character progress for Personal65 artist imports.

The in-progress file is NOT an installation-success or image-likeness receipt.
It contains no artwork, credentials, network responses or imported files.
Each update is persisted via an atomic replace + fsync in the user's local
portable data folder, so completed character attempts survive interruption.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import uuid


class PersonalInstallJournal:
    def __init__(self, directory, summary):
        root = Path(directory)
        if root.is_symlink() or (root.exists() and not root.is_dir()):
            raise ValueError("Install receipt root must be a real directory")
        root.mkdir(parents=True, exist_ok=True)
        self.path = root / (
            "personal65-batch-" +
            datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") +
            "-" + uuid.uuid4().hex[:8] + ".json"
        )
        self.state = {
            "schema": 1,
            "scope": "local_only_unverified_progress",
            "plan_summary": summary,
            "completed_character_attempts": [],
            "final_installation": None,
            "finished": False,
            "likeness_approved": False,
            "rights_approved": False,
        }
        self._save()

    def record_character(self, entry):
        if self.state["finished"]:
            raise ValueError("Cannot append to finalized journal")
        if (not isinstance(entry, dict) or
                not isinstance(entry.get("profile"), str) or
                entry.get("status") not in (
                    "pending_inventory_validation", "failed")):
            raise ValueError("Invalid provisional creator import checkpoint")
        self.state["completed_character_attempts"].append(entry.copy())
        self._save()

    def finalize(self, installation):
        if not isinstance(installation, dict):
            raise ValueError("Invalid final personal installation receipt")
        self.state["final_installation"] = installation
        self.state["finished"] = True
        self.state["scope"] = "local_only_structural_inventory_checked"
        self._save()

    def _save(self):
        temporary = self.path.with_name(
            self.path.name + "." + uuid.uuid4().hex[:8] + ".tmp")
        try:
            with temporary.open("x", encoding="utf-8", newline="\n") as stream:
                json.dump(self.state, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            if temporary.exists():
                temporary.unlink()

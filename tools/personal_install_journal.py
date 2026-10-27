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
import re
from pathlib import Path
import uuid


class PersonalInstallJournal:
    def __init__(self, directory, summary, *, planned_profiles=None):
        # Persist the EXACT opt-in scope. A two-role trial must not be
        # recoverable as an unbounded 65-role download batch.
        if planned_profiles is not None:
            if (not isinstance(planned_profiles, (tuple, list)) or
                    len(planned_profiles) > _MAX_CHARACTERS or
                    any(not isinstance(p, str) or not p or len(p) > 128
                        for p in planned_profiles) or
                    len(set(planned_profiles)) != len(planned_profiles)):
                raise ValueError("Invalid selected personal role scope")
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
        if planned_profiles is not None:
            self.state["planned_profiles"] = list(planned_profiles)
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


# Read only our exact journal filenames, never arbitrary local JSON. The
# format is intentionally small: personal art pixels are never recorded.
_JOURNAL_PATTERN = re.compile(
    r"^personal65-batch-[0-9]{8}-[0-9]{6}-[0-9a-f]{8}\.json$")
_MAX_READ_BYTES = 4 * 1024 * 1024
_MAX_CHARACTERS = 123


def latest_install_journal(directory):
    """Read the newest valid, bounded, NON-LINKED R14+ journal or return None.

    Invalid, unfinished temporary, old legacy and symlinked files are ignored.
    The result contains only local attempt metadata; no external fetching.
    """
    root = Path(directory)
    if not root.exists():
        return None
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Personal journal directory must not be linked")
    items = []
    for p in root.iterdir():
        if (_JOURNAL_PATTERN.fullmatch(p.name) and not p.is_symlink()
                and p.is_file()):
            items.append(p)
    for path in sorted(items, key=lambda p: p.name, reverse=True)[:50]:
        try:
            if not 10 <= path.stat().st_size <= _MAX_READ_BYTES:
                continue
            doc = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(doc, dict) or type(doc.get("schema")) is not int or doc["schema"] != 1:
                continue
            if type(doc.get("finished")) is not bool:
                continue
            records = doc.get("completed_character_attempts")
            if not isinstance(records, list) or len(records) > _MAX_CHARACTERS:
                continue
            if not isinstance(doc.get("plan_summary"), dict):
                continue
            planned = doc.get("planned_profiles")
            if "planned_profiles" in doc and (
                    not isinstance(planned, list) or
                    len(planned) > _MAX_CHARACTERS or
                    any(not isinstance(p, str) or not p or len(p) > 128
                        for p in planned) or
                    len(set(planned)) != len(planned)):
                continue
            if any(
                    not isinstance(r, dict)
                    or not isinstance(r.get("profile"), str)
                    or r.get("status") not in
                    ("failed", "pending_inventory_validation")
                    for r in records):
                continue
            if doc["finished"]:
                final = doc.get("final_installation")
                if not isinstance(final, dict):
                    continue
                results = final.get("results")
                if not isinstance(results, list) or len(results) > _MAX_CHARACTERS:
                    continue
            else:
                if doc.get("final_installation") is not None:
                    continue
            return {"path": str(path), "finished": doc["finished"],
                    "attempts": len(records),
                    "completed_character_attempts": records,
                    "planned_profiles": planned,
                    "final_installation": doc.get("final_installation"),
                    "plan_summary": doc["plan_summary"]}
        except (OSError, UnicodeError, ValueError, TypeError,
                json.JSONDecodeError):
            continue
    return None


def restartable_profiles(journal, current_plan):
    """Select only currently uninstalled profiles with approved pinned installers.

    Incomplete runs resume ONLY the persisted original selection. Older R14/R15
    journals had no selection scope; for those, conservatively retry only
    already attempted profiles, never every profile in the entire roster.
    For finished runs, retry only recorded failures. Current native inventory
    and current allowlisted sources always remain authoritative.
    """
    if not isinstance(journal, dict):
        raise ValueError("No validated local journal")
    characters = current_plan.get("characters")
    if not isinstance(characters, list):
        raise ValueError("Invalid current source planning")
    permitted = {c["profile"] for c in characters
                 if c.get("status") == "ready_for_opt_in"}
    if not journal.get("finished"):
        scoped = journal.get("planned_profiles")
        if scoped is None:
            # Legacy journals did not retain the original trial size/filter.
            # We cannot safely infer which unattempted roles the user approved.
            scoped = [r.get("profile") for r in
                      journal.get("completed_character_attempts", [])
                      if isinstance(r, dict)]
        if not isinstance(scoped, list):
            raise ValueError("Invalid saved creator import scope")
        return sorted(permitted.intersection(
            p for p in scoped if isinstance(p, str)))
    final = journal.get("final_installation")
    if not isinstance(final, dict):
        raise ValueError("Final receipt is missing")
    return sorted({
        row["profile"]
        for row in final.get("results", [])
        if isinstance(row, dict) and row.get("status") == "failed"
        and isinstance(row.get("profile"), str)
        and row["profile"] in permitted
    })

"""Character-scoped local conversation history and user-approved memories.

All data stays in the user's DyberPet configuration directory. Memory writes
are explicit UI actions; model output never writes or deletes memory by itself.
"""
from __future__ import annotations

import re
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

from .preferences import default_preference_path

MAX_TEXT = 4000
MAX_MEMORY = 500
MAX_MESSAGES_PER_ROLE = 4000


def default_store_path() -> Path:
    return default_preference_path().parent / "companion.sqlite3"


def _clean_text(value: str, *, limit: int, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(field + " must be text")
    value = value.strip()
    if not value or len(value) > limit:
        raise ValueError(field + " must contain 1–" + str(limit) + " characters")
    return value


def _tokens(text: str) -> set[str]:
    tokens: set[str] = set()
    for match in re.finditer(r"[A-Za-z0-9_]{2,}|[\u3400-\u9fff]+", text.casefold()):
        value = match.group(0)
        if "\u3400" <= value[0] <= "\u9fff":
            tokens.update(value[i:i + 2] for i in range(max(1, len(value) - 1)))
            if len(value) == 1:
                tokens.add(value)
        else:
            tokens.add(value)
    return tokens


class CompanionStore:
    """SQLite store with per-character isolation and bounded retrieval."""

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path is not None else default_store_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.is_symlink():
            raise ValueError("Companion database path cannot be a symlink")
        self._initialize()

    @contextmanager
    def _connect(self):
        if self.path.is_symlink():
            raise ValueError("Companion database path cannot be a symlink")
        connection = sqlite3.connect(str(self.path), timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=5000")
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self):
        with self._connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("PRAGMA synchronous=FULL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    character TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('user','assistant')),
                    content TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('complete','interrupted')),
                    turn_id TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_messages_character_id
                    ON messages(character, id);
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    character TEXT NOT NULL,
                    content TEXT NOT NULL,
                    importance INTEGER NOT NULL CHECK(importance BETWEEN 1 AND 3),
                    pinned INTEGER NOT NULL DEFAULT 0 CHECK(pinned IN (0,1)),
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_memories_character
                    ON memories(character, pinned, importance, updated_at);
            """)
        try:
            self.path.chmod(0o600)
        except OSError:
            pass

    @staticmethod
    def _character(character: str) -> str:
        return _clean_text(character, limit=120, field="character")

    def append_turn(self, character: str, user_text: str, assistant_text: str) -> str:
        character = self._character(character)
        user_text = _clean_text(user_text, limit=MAX_TEXT, field="user message")
        assistant_text = _clean_text(assistant_text, limit=MAX_TEXT, field="assistant message")
        turn_id = uuid.uuid4().hex
        now = time.time()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.executemany(
                "INSERT INTO messages(character,role,content,created_at,status,turn_id) "
                "VALUES(?,?,?,?,?,?)",
                [(character, "user", user_text, now, "complete", turn_id),
                 (character, "assistant", assistant_text, now, "complete", turn_id)],
            )
            db.execute("""
                DELETE FROM messages
                WHERE character=? AND id NOT IN (
                    SELECT id FROM messages WHERE character=?
                    ORDER BY id DESC LIMIT ?
                )
            """, (character, character, MAX_MESSAGES_PER_ROLE))
        return turn_id

    def recent_messages(self, character: str, *, limit: int = 12) -> list[dict]:
        character = self._character(character)
        if type(limit) is not int or not 1 <= limit <= 50:
            raise ValueError("history limit must be 1–50")
        with self._connect() as db:
            rows = db.execute("""
                SELECT role,content,created_at FROM messages
                WHERE character=? AND status='complete'
                ORDER BY id DESC LIMIT ?
            """, (character, limit)).fetchall()
        return [{"role": row["role"], "content": row["content"],
                 "created_at": row["created_at"]} for row in reversed(rows)]

    def add_memory(self, character: str, content: str, *, importance: int = 2,
                   pinned: bool = False) -> dict:
        character = self._character(character)
        content = _clean_text(content, limit=MAX_TEXT, field="memory")
        if type(importance) is not int or not 1 <= importance <= 3:
            raise ValueError("memory importance must be 1–3")
        if type(pinned) is not bool:
            raise ValueError("pinned must be boolean")
        now = time.time()
        memory_id = uuid.uuid4().hex
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute("""
                SELECT id FROM memories WHERE character=? AND lower(trim(content))=lower(trim(?))
            """, (character, content)).fetchone()
            if existing:
                db.execute("""
                    UPDATE memories SET importance=?,pinned=?,updated_at=?
                    WHERE id=? AND character=?
                """, (importance, int(pinned), now, existing["id"], character))
                memory_id = existing["id"]
            else:
                count = db.execute(
                    "SELECT COUNT(*) FROM memories WHERE character=?", (character,)
                ).fetchone()[0]
                if count >= MAX_MEMORY:
                    raise ValueError("This character already has 500 memories; remove an old one first")
                db.execute("""
                    INSERT INTO memories(id,character,content,importance,pinned,created_at,updated_at)
                    VALUES(?,?,?,?,?,?,?)
                """, (memory_id, character, content, importance, int(pinned), now, now))
        return {"id": memory_id, "character": character, "content": content,
                "importance": importance, "pinned": pinned, "updated_at": now}

    def list_memories(self, character: str, *, limit: int = 100) -> list[dict]:
        character = self._character(character)
        if type(limit) is not int or not 1 <= limit <= 500:
            raise ValueError("memory list limit must be 1–500")
        with self._connect() as db:
            rows = db.execute("""
                SELECT id,content,importance,pinned,created_at,updated_at
                FROM memories WHERE character=?
                ORDER BY pinned DESC,importance DESC,updated_at DESC LIMIT ?
            """, (character, limit)).fetchall()
        return [dict(row) for row in rows]

    def delete_memory(self, character: str, memory_id: str) -> bool:
        character = self._character(character)
        if not isinstance(memory_id, str) or not re.fullmatch(r"[0-9a-f]{32}", memory_id):
            raise ValueError("invalid memory id")
        with self._connect() as db:
            cursor = db.execute(
                "DELETE FROM memories WHERE character=? AND id=?", (character, memory_id)
            )
        return cursor.rowcount == 1

    def search_memories(self, character: str, query: str, *, limit: int = 5) -> list[dict]:
        character = self._character(character)
        query = _clean_text(query, limit=MAX_TEXT, field="memory query")
        if type(limit) is not int or not 1 <= limit <= 20:
            raise ValueError("memory search limit must be 1–20")
        query_tokens = _tokens(query)
        rows = self.list_memories(character, limit=MAX_MEMORY)
        ranked = []
        for row in rows:
            memory_tokens = _tokens(row["content"])
            overlap = len(query_tokens & memory_tokens)
            exact = query.casefold() in row["content"].casefold()
            if not overlap and not exact and not row["pinned"]:
                continue
            score = overlap / max(1, len(query_tokens))
            score += 1.5 if exact else 0
            score += 0.35 * row["importance"] + (0.75 if row["pinned"] else 0)
            row["score"] = score
            ranked.append(row)
        ranked.sort(key=lambda item: (item["score"], item["updated_at"]), reverse=True)
        return ranked[:limit]

    def memory_context(self, character: str, query: str, *, limit: int = 5,
                       max_chars: int = 1800) -> str:
        memories = self.search_memories(character, query, limit=limit)
        if not memories:
            return ""
        lines = []
        remaining = max_chars
        for item in memories:
            line = "- " + item["content"]
            if len(line) > remaining:
                continue
            lines.append(line)
            remaining -= len(line) + 1
        if not lines:
            return ""
        return "\n".join(lines)

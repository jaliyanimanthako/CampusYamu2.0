"""Where the course chat's memory lives.

Three tables (supabase/migrations/ has the Postgres version):

    chat_conversations  one per student per course offering (user_id, uni_code): running summary and
                        how far the summary / the fact extraction have read (message seq numbers)
    chat_messages       every question and answer, numbered 1, 2, 3 ... within its conversation
    student_facts       short lasting facts about the student, shared by all their course chats
    daily_usage         how many paid calls each student made per day (chat, AI search, research)
    student_results     each student's latest search: the form they sent and the report (one row each)

MemoryStore keeps them in a SQLite file (development and tests). PostgresMemoryStore keeps them in
Supabase Postgres; open_store() picks it when SUPABASE_DB_URL is set. Both run the same SQL (only the
parameter marker differs), and every method opens its own connection or takes one from the pool, so the
store can be used from the API thread and the background memory thread at once.
"""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

from campusyamu.core import settings
from campusyamu.core.paths import PROJECT_ROOT

SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS chat_conversations (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    uni_code TEXT NOT NULL,
    course_code TEXT NOT NULL DEFAULT '',
    course_name TEXT NOT NULL DEFAULT '',
    university TEXT NOT NULL DEFAULT '',
    summary TEXT NOT NULL DEFAULT '',
    summarized_through INTEGER NOT NULL DEFAULT 0,
    facts_through INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (user_id, uni_code)
);
CREATE TABLE IF NOT EXISTS chat_messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES chat_conversations(id) ON DELETE CASCADE,
    seq INTEGER NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    sources TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    UNIQUE (conversation_id, seq)
);
CREATE TABLE IF NOT EXISTS student_facts (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    fact TEXT NOT NULL,
    category TEXT NOT NULL,
    source_uni_code TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS student_facts_user ON student_facts (user_id);
CREATE TABLE IF NOT EXISTS student_results (
    user_id TEXT PRIMARY KEY,
    form TEXT NOT NULL,
    report TEXT NOT NULL,
    used_llm INTEGER NOT NULL DEFAULT 0,
    saved_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS daily_usage (
    user_id TEXT NOT NULL,
    day TEXT NOT NULL,
    action TEXT NOT NULL,
    used INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, day, action)
);
"""

JSON_COLUMNS = ("sources", "form", "report")             # JSON text in SQLite, jsonb in Postgres
CONVERSATION_COLUMNS = ("id, user_id, uni_code, course_code, course_name, university, summary, "
                        "summarized_through, facts_through, created_at, updated_at")


def _now(step: int = 0) -> str:
    """UTC now as ISO text; `step` microseconds later keeps rows written in one batch in order."""

    return (datetime.now(timezone.utc) + timedelta(microseconds=step)).isoformat()


def default_db_path() -> Path:
    path = Path(settings.get("memory.db", "data/memory/chat_memory.db"))
    return path if path.is_absolute() else PROJECT_ROOT / path


class MemoryStore:
    """SQLite version (one file). Methods take plain strings and return plain dicts."""

    marker = "?"

    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path) if path else default_db_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._tx() as conn:
            conn.executescript(SQLITE_SCHEMA)

    # --- plumbing -----------------------------------------------------------------------
    @contextmanager
    def _tx(self) -> Iterator[Any]:
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _sql(self, sql: str) -> str:
        return sql if self.marker == "?" else sql.replace("?", self.marker)

    def _all(self, conn: Any, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        return [self._row(r) for r in conn.execute(self._sql(sql), params).fetchall()]

    def _one(self, conn: Any, sql: str, params: tuple = ()) -> dict[str, Any] | None:
        rows = self._all(conn, sql, params)
        return rows[0] if rows else None

    def _run(self, conn: Any, sql: str, params: tuple = ()) -> int:
        return conn.execute(self._sql(sql), params).rowcount

    @staticmethod
    def _row(row: Any) -> dict[str, Any]:
        out = {}
        for key, value in dict(row).items():
            if isinstance(value, uuid.UUID):
                value = str(value)
            elif isinstance(value, datetime):
                value = value.isoformat()
            elif key in JSON_COLUMNS and isinstance(value, str):
                value = json.loads(value or "null")
            out[key] = value
        return out

    # --- conversations ------------------------------------------------------------------
    def conversation(self, user_id: str, uni_code: str) -> dict[str, Any] | None:
        with self._tx() as conn:
            return self._one(conn, f"SELECT {CONVERSATION_COLUMNS} FROM chat_conversations "
                                   "WHERE user_id = ? AND uni_code = ?", (user_id, uni_code))

    def ensure_conversation(self, user_id: str, course: dict[str, Any]) -> dict[str, Any]:
        uni_code = str(course["uni_code"])
        now = _now()
        with self._tx() as conn:
            self._run(conn, "INSERT INTO chat_conversations (id, user_id, uni_code, course_code, course_name, "
                            "university, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
                            "ON CONFLICT (user_id, uni_code) DO NOTHING",
                      (str(uuid.uuid4()), user_id, uni_code, str(course.get("course_code") or ""),
                       str(course.get("course_name") or ""), str(course.get("university") or ""), now, now))
            return self._one(conn, f"SELECT {CONVERSATION_COLUMNS} FROM chat_conversations "
                                   "WHERE user_id = ? AND uni_code = ?", (user_id, uni_code))

    def conversations(self, user_id: str) -> list[dict[str, Any]]:
        """The student's course chats, most recent first, with the message count."""

        with self._tx() as conn:
            return self._all(conn, f"SELECT {', '.join('c.' + c.strip() for c in CONVERSATION_COLUMNS.split(','))}, "
                                   "(SELECT COUNT(*) FROM chat_messages m WHERE m.conversation_id = c.id) AS messages "
                                   "FROM chat_conversations c WHERE c.user_id = ? ORDER BY c.updated_at DESC",
                             (user_id,))

    def delete_conversation(self, user_id: str, uni_code: str) -> bool:
        with self._tx() as conn:
            return self._run(conn, "DELETE FROM chat_conversations WHERE user_id = ? AND uni_code = ?",
                             (user_id, uni_code)) > 0

    def set_summary(self, conversation_id: str, summary: str, through: int) -> None:
        with self._tx() as conn:
            self._run(conn, "UPDATE chat_conversations SET summary = ?, summarized_through = ? WHERE id = ?",
                      (summary, through, conversation_id))

    def set_facts_through(self, conversation_id: str, through: int) -> None:
        with self._tx() as conn:
            self._run(conn, "UPDATE chat_conversations SET facts_through = ? WHERE id = ?", (through, conversation_id))

    # --- messages -----------------------------------------------------------------------
    def add_messages(self, conversation_id: str, messages: list[dict[str, Any]]) -> list[int]:
        """Append messages ({role, content, sources?}) in order; returns their seq numbers."""

        now = _now()
        with self._tx() as conn:
            # touching the conversation first locks it, so two writers cannot take the same seq
            self._run(conn, "UPDATE chat_conversations SET updated_at = ? WHERE id = ?", (now, conversation_id))
            last = self._one(conn, "SELECT COALESCE(MAX(seq), 0) AS last_seq FROM chat_messages "
                                   "WHERE conversation_id = ?", (conversation_id,))["last_seq"]
            seqs = []
            for i, message in enumerate(messages, 1):
                self._run(conn, "INSERT INTO chat_messages (id, conversation_id, seq, role, content, sources, "
                                "created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                          (str(uuid.uuid4()), conversation_id, last + i, message["role"], message["content"],
                           json.dumps(message.get("sources") or [], ensure_ascii=False), now))
                seqs.append(last + i)
            return seqs

    def messages(self, conversation_id: str, after: int = 0, limit: int | None = None,
                 before: int | None = None) -> list[dict[str, Any]]:
        """Messages with after < seq (< before), oldest first; with limit, the newest `limit` of them."""

        sql = "SELECT seq, role, content, sources, created_at FROM chat_messages WHERE conversation_id = ? AND seq > ?"
        params: tuple = (conversation_id, after)
        if before is not None:
            sql += " AND seq < ?"
            params += (before,)
        sql += " ORDER BY seq DESC"
        if limit is not None:
            sql += " LIMIT ?"
            params += (int(limit),)
        with self._tx() as conn:
            return list(reversed(self._all(conn, sql, params)))

    # --- student facts ------------------------------------------------------------------
    def facts(self, user_id: str) -> list[dict[str, Any]]:
        """The student's facts, oldest first."""

        with self._tx() as conn:
            return self._all(conn, "SELECT id, fact, category, source_uni_code, created_at, updated_at "
                                   "FROM student_facts WHERE user_id = ? ORDER BY created_at, id", (user_id,))

    def change_facts(self, user_id: str, add: list[dict[str, str]] = (), update: list[dict[str, str]] = (),
                     remove: list[str] = (), keep: int | None = None) -> None:
        """Apply one set of changes; with keep, drop the oldest facts beyond that many."""

        now = _now()
        with self._tx() as conn:
            for fact_id in remove:
                self._run(conn, "DELETE FROM student_facts WHERE id = ? AND user_id = ?", (fact_id, user_id))
            for item in update:
                self._run(conn, "UPDATE student_facts SET fact = ?, category = ?, updated_at = ? "
                                "WHERE id = ? AND user_id = ?",
                          (item["fact"], item["category"], now, item["id"], user_id))
            for i, item in enumerate(add, 1):
                stamp = _now(i)
                self._run(conn, "INSERT INTO student_facts (id, user_id, fact, category, source_uni_code, "
                                "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                          (str(uuid.uuid4()), user_id, item["fact"], item["category"],
                           str(item.get("source_uni_code") or ""), stamp, stamp))
            if keep is not None:
                rows = self._all(conn, "SELECT id FROM student_facts WHERE user_id = ? "
                                       "ORDER BY updated_at DESC, created_at DESC, id", (user_id,))
                for row in rows[keep:]:
                    self._run(conn, "DELETE FROM student_facts WHERE id = ?", (row["id"],))

    def delete_fact(self, user_id: str, fact_id: str) -> bool:
        with self._tx() as conn:
            return self._run(conn, "DELETE FROM student_facts WHERE id = ? AND user_id = ?", (fact_id, user_id)) > 0

    # --- the student's latest search ------------------------------------------------------
    def save_results(self, user_id: str, form: dict[str, Any], report: dict[str, Any], used_llm: bool) -> str:
        """Keep this search as the student's latest (replacing the one before); returns saved_at."""

        now = _now()
        with self._tx() as conn:
            self._run(conn, "INSERT INTO student_results (user_id, form, report, used_llm, saved_at) "
                            "VALUES (?, ?, ?, ?, ?) ON CONFLICT (user_id) DO UPDATE SET form = excluded.form, "
                            "report = excluded.report, used_llm = excluded.used_llm, saved_at = excluded.saved_at",
                      (user_id, json.dumps(form, ensure_ascii=False, default=str),
                       json.dumps(report, ensure_ascii=False, default=str), 1 if used_llm else 0, now))
        return now

    def results(self, user_id: str) -> dict[str, Any] | None:
        """{form, report, used_llm, saved_at} of the student's latest search, or None."""

        with self._tx() as conn:
            row = self._one(conn, "SELECT form, report, used_llm, saved_at FROM student_results WHERE user_id = ?",
                            (user_id,))
        if row is not None:
            row["used_llm"] = bool(row["used_llm"])
        return row

    # --- daily usage (limits) ----------------------------------------------------------
    def usage(self, user_id: str, day: str) -> dict[str, int]:
        """{action: count} for one student on one day (YYYY-MM-DD)."""

        with self._tx() as conn:
            rows = self._all(conn, "SELECT action, used FROM daily_usage WHERE user_id = ? AND day = ?", (user_id, day))
        return {r["action"]: int(r["used"]) for r in rows}

    def add_usage(self, user_id: str, action: str, day: str) -> int:
        """Count one more; returns the new count for that day."""

        with self._tx() as conn:
            self._run(conn, "INSERT INTO daily_usage (user_id, day, action, used) VALUES (?, ?, ?, 1) "
                            "ON CONFLICT (user_id, day, action) DO UPDATE SET used = daily_usage.used + 1",
                      (user_id, day, action))
            return int(self._one(conn, "SELECT used FROM daily_usage WHERE user_id = ? AND day = ? AND action = ?",
                                 (user_id, day, action))["used"])

    def delete_user(self, user_id: str) -> None:
        """Everything this store keeps about one student (account deletion)."""

        with self._tx() as conn:
            self._run(conn, "DELETE FROM chat_conversations WHERE user_id = ?", (user_id,))   # messages cascade
            self._run(conn, "DELETE FROM student_facts WHERE user_id = ?", (user_id,))
            self._run(conn, "DELETE FROM daily_usage WHERE user_id = ?", (user_id,))
            self._run(conn, "DELETE FROM student_results WHERE user_id = ?", (user_id,))

    def close(self) -> None:
        pass


class PostgresMemoryStore(MemoryStore):
    """Supabase Postgres. The tables come from supabase/migrations/ (not created here). Connects as the
    server (SUPABASE_DB_URL), so Row Level Security does not apply; the API checks who may see what."""

    marker = "%s"

    def __init__(self, url: str, min_size: int = 1, max_size: int = 4) -> None:
        try:
            from psycopg.rows import dict_row
            from psycopg_pool import ConnectionPool
        except ImportError as exc:                      # pragma: no cover - dependency is in pyproject
            raise RuntimeError("SUPABASE_DB_URL is set but psycopg is not installed (uv sync)") from exc
        # prepare_threshold=None: the Supabase pooler (transaction mode) does not keep prepared statements
        self.pool = ConnectionPool(url, min_size=min_size, max_size=max_size, open=True,
                                   kwargs={"row_factory": dict_row, "prepare_threshold": None})

    @contextmanager
    def _tx(self) -> Iterator[Any]:
        with self.pool.connection() as conn:            # commits on success, rolls back on error
            yield conn

    def close(self) -> None:
        self.pool.close()


def open_store() -> MemoryStore:
    """Supabase Postgres when SUPABASE_DB_URL is set, otherwise the SQLite file (memory.db in settings)."""

    url = os.getenv("SUPABASE_DB_URL")
    return PostgresMemoryStore(url) if url else MemoryStore()

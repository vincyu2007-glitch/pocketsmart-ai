"""SQLite persistence for users and saved recommendations.

Deliberately dependency-free: one short-lived connection per operation, WAL
mode, and parameterised statements throughout.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT    NOT NULL,
    email         TEXT    NOT NULL UNIQUE,
    password_hash TEXT    NOT NULL,
    created_at    TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS recommendations (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER REFERENCES users(id) ON DELETE CASCADE,
    plan_type  TEXT    NOT NULL,
    title      TEXT    NOT NULL,
    budget     INTEGER NOT NULL,
    payload    TEXT    NOT NULL,
    source     TEXT    NOT NULL DEFAULT 'ai',
    created_at TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_reco_user    ON recommendations(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_reco_created ON recommendations(created_at DESC);
"""


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db(db_path: str | Path) -> None:
    with connect(db_path) as conn:
        conn.executescript(SCHEMA)


# --- users -----------------------------------------------------------------
def create_user(db_path: str | Path, name: str, email: str, password_hash: str) -> dict | None:
    """Insert a user. Returns ``None`` if the email is already registered."""
    with connect(db_path) as conn:
        try:
            cursor = conn.execute(
                "INSERT INTO users (name, email, password_hash, created_at) VALUES (?,?,?,?)",
                (name, email.lower(), password_hash, utcnow()),
            )
        except sqlite3.IntegrityError:
            return None
        row = conn.execute("SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return dict(row) if row else None


def get_user_by_email(db_path: str | Path, email: str) -> dict | None:
    with connect(db_path) as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email.lower(),)).fetchone()
    return dict(row) if row else None


def get_user(db_path: str | Path, user_id: int) -> dict | None:
    with connect(db_path) as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return dict(row) if row else None


def email_exists(db_path: str | Path, email: str) -> bool:
    return get_user_by_email(db_path, email) is not None


# --- recommendations -------------------------------------------------------
def save_recommendation(
    db_path: str | Path,
    *,
    user_id: int | None,
    plan_type: str,
    title: str,
    budget: int,
    payload: dict[str, Any],
    source: str = "ai",
) -> int:
    with connect(db_path) as conn:
        cursor = conn.execute(
            "INSERT INTO recommendations (user_id, plan_type, title, budget, payload, source, created_at)"
            " VALUES (?,?,?,?,?,?,?)",
            (user_id, plan_type, title[:200], int(budget), json.dumps(payload), source, utcnow()),
        )
        return int(cursor.lastrowid)


def list_recommendations(
    db_path: str | Path,
    *,
    user_id: int | None,
    limit: int = 25,
    offset: int = 0,
    plan_type: str | None = None,
) -> list[dict[str, Any]]:
    clauses, params = [], []
    if user_id is not None:
        clauses.append("user_id = ?")
        params.append(user_id)
    if plan_type:
        clauses.append("plan_type = ?")
        params.append(plan_type)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.extend([int(limit), int(offset)])
    with connect(db_path) as conn:
        rows = conn.execute(
            f"SELECT id, plan_type, title, budget, source, created_at FROM recommendations"
            f" {where} ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
    return [dict(row) for row in rows]


def get_recommendation(
    db_path: str | Path, rec_id: int, *, user_id: int | None = None
) -> dict[str, Any] | None:
    query = "SELECT * FROM recommendations WHERE id = ?"
    params: Iterable[Any] = [int(rec_id)]
    if user_id is not None:
        query += " AND user_id = ?"
        params = [int(rec_id), int(user_id)]
    with connect(db_path) as conn:
        row = conn.execute(query, list(params)).fetchone()
    if not row:
        return None
    record = dict(row)
    try:
        record["payload"] = json.loads(record["payload"])
    except (json.JSONDecodeError, TypeError):
        record["payload"] = {}
    record["created_at_display"] = _display_time(record.get("created_at"))
    return record


def delete_recommendation(db_path: str | Path, rec_id: int, *, user_id: int | None = None) -> bool:
    query = "DELETE FROM recommendations WHERE id = ?"
    params: list[Any] = [int(rec_id)]
    if user_id is not None:
        query += " AND user_id = ?"
        params.append(int(user_id))
    with connect(db_path) as conn:
        cursor = conn.execute(query, params)
        return cursor.rowcount > 0


def count_recommendations(db_path: str | Path, user_id: int | None) -> int:
    if user_id is None:
        with connect(db_path) as conn:
            return int(conn.execute("SELECT COUNT(*) AS c FROM recommendations").fetchone()["c"])
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM recommendations WHERE user_id = ?", (user_id,)
        ).fetchone()
    return int(row["c"])


def _display_time(value: str | None) -> str:
    if not value:
        return ""
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return value
    return parsed.strftime("%d %b %Y, %I:%M %p").replace("AM", "am").replace("PM", "pm")

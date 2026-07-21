"""SQLite connection and schema for learning progress (Sprint 3)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS learning_unit_progress (
    learning_unit_id TEXT PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'new',
    times_completed INTEGER NOT NULL DEFAULT 0,
    last_completed TEXT,
    next_revision TEXT,
    interval_days INTEGER NOT NULL DEFAULT 0,
    ease_factor REAL NOT NULL DEFAULT 2.5,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS split_preference (
    parent_clause_id TEXT PRIMARY KEY,
    mode TEXT NOT NULL CHECK (mode IN ('whole', 'letters')),
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS article_gloss (
    article_number TEXT PRIMARY KEY,
    text TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS unit_modes_seen (
    learning_unit_id TEXT NOT NULL,
    mode TEXT NOT NULL,
    seen_at TEXT NOT NULL,
    PRIMARY KEY (learning_unit_id, mode)
);

CREATE INDEX IF NOT EXISTS idx_progress_status
    ON learning_unit_progress(status);
CREATE INDEX IF NOT EXISTS idx_progress_next_revision
    ON learning_unit_progress(next_revision);
CREATE INDEX IF NOT EXISTS idx_modes_seen_unit
    ON unit_modes_seen(learning_unit_id);
"""


def connect(db_path: Path | str) -> sqlite3.Connection:
    """Open a SQLite connection with row factory and foreign keys on."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # check_same_thread=False: FastAPI/uvicorn may touch the connection
    # from worker threads (including TestClient).
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """Create progress tables if missing."""
    conn.executescript(SCHEMA_SQL)
    conn.commit()


def open_progress_db(db_path: Path | str) -> sqlite3.Connection:
    """Connect and ensure schema exists."""
    conn = connect(db_path)
    init_db(conn)
    return conn

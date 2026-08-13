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

CREATE TABLE IF NOT EXISTS memory_entry (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    acronym TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    logged_date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'new',
    interval_days INTEGER NOT NULL DEFAULT 0,
    last_completed TEXT,
    next_revision TEXT,
    times_completed INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS memory_media (
    entry_id TEXT PRIMARY KEY,
    path TEXT NOT NULL,
    uploaded_at TEXT NOT NULL,
    FOREIGN KEY (entry_id) REFERENCES memory_entry(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_memory_next_revision
    ON memory_entry(next_revision);
CREATE INDEX IF NOT EXISTS idx_memory_logged_date
    ON memory_entry(logged_date);
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


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,),
    ).fetchone()
    return row is not None


def _pk_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    info = conn.execute(f"PRAGMA table_info({table})").fetchall()
    ranked = [(int(row["pk"]), str(row["name"])) for row in info if row["pk"]]
    ranked.sort()
    return [name for _pk, name in ranked]


def _has_unique_on(conn: sqlite3.Connection, table: str, columns: list[str]) -> bool:
    """True when table has a PRIMARY KEY or UNIQUE index on exactly ``columns``."""
    if _pk_columns(conn, table) == columns:
        return True
    for index in conn.execute(f"PRAGMA index_list({table})").fetchall():
        if not index["unique"]:
            continue
        index_cols = [
            str(row["name"])
            for row in conn.execute(f"PRAGMA index_info({index['name']})").fetchall()
        ]
        if index_cols == columns:
            return True
    return False


def _rebuild_unit_modes_seen(conn: sqlite3.Connection) -> None:
    """Add the composite key required by mark_mode_seen upserts."""
    conn.execute("DROP INDEX IF EXISTS idx_modes_seen_unit")
    conn.execute(
        """
        CREATE TABLE unit_modes_seen_new (
            learning_unit_id TEXT NOT NULL,
            mode TEXT NOT NULL,
            seen_at TEXT NOT NULL,
            PRIMARY KEY (learning_unit_id, mode)
        )
        """
    )
    conn.execute(
        """
        INSERT OR REPLACE INTO unit_modes_seen_new
            (learning_unit_id, mode, seen_at)
        SELECT learning_unit_id, mode, MAX(seen_at)
        FROM unit_modes_seen
        GROUP BY learning_unit_id, mode
        """
    )
    conn.execute("DROP TABLE unit_modes_seen")
    conn.execute("ALTER TABLE unit_modes_seen_new RENAME TO unit_modes_seen")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_modes_seen_unit "
        "ON unit_modes_seen(learning_unit_id)"
    )


def _rebuild_app_settings(conn: sqlite3.Connection) -> None:
    """Add the key primary key required by settings upserts."""
    conn.execute(
        """
        CREATE TABLE app_settings_new (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        INSERT OR REPLACE INTO app_settings_new (key, value, updated_at)
        SELECT key, value, updated_at
        FROM app_settings
        WHERE rowid IN (SELECT MAX(rowid) FROM app_settings GROUP BY key)
        """
    )
    conn.execute("DROP TABLE app_settings")
    conn.execute("ALTER TABLE app_settings_new RENAME TO app_settings")


def migrate_schema(conn: sqlite3.Connection) -> None:
    """Upgrade tables created before PRIMARY KEYs existed.

    ``CREATE TABLE IF NOT EXISTS`` does not alter an older ``unit_modes_seen``
    or ``app_settings`` table. Learn then 500s on ON CONFLICT upserts.
    """
    if _table_exists(conn, "unit_modes_seen") and not _has_unique_on(
        conn, "unit_modes_seen", ["learning_unit_id", "mode"]
    ):
        _rebuild_unit_modes_seen(conn)
    if _table_exists(conn, "app_settings") and not _has_unique_on(
        conn, "app_settings", ["key"]
    ):
        _rebuild_app_settings(conn)


def init_db(conn: sqlite3.Connection) -> None:
    """Create progress tables if missing and migrate older local DBs."""
    conn.executescript(SCHEMA_SQL)
    migrate_schema(conn)
    conn.commit()


def open_progress_db(db_path: Path | str) -> sqlite3.Connection:
    """Connect and ensure schema exists."""
    conn = connect(db_path)
    init_db(conn)
    return conn

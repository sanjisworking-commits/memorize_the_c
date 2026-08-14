"""SQLite connection and schema for learning progress (user-scoped)."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from constitution_memorizer.progress.user_ids import LOCAL_USER_ID

logger = logging.getLogger(__name__)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS learning_unit_progress (
    user_id TEXT NOT NULL,
    learning_unit_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'new',
    times_completed INTEGER NOT NULL DEFAULT 0,
    last_completed TEXT,
    next_revision TEXT,
    interval_days INTEGER NOT NULL DEFAULT 0,
    ease_factor REAL NOT NULL DEFAULT 2.5,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (user_id, learning_unit_id)
);

CREATE TABLE IF NOT EXISTS split_preference (
    user_id TEXT NOT NULL,
    parent_clause_id TEXT NOT NULL,
    mode TEXT NOT NULL CHECK (mode IN ('whole', 'letters')),
    updated_at TEXT NOT NULL,
    PRIMARY KEY (user_id, parent_clause_id)
);

CREATE TABLE IF NOT EXISTS article_gloss (
    user_id TEXT NOT NULL,
    article_number TEXT NOT NULL,
    text TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (user_id, article_number)
);

CREATE TABLE IF NOT EXISTS app_settings (
    user_id TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (user_id, key)
);

CREATE TABLE IF NOT EXISTS unit_modes_seen (
    user_id TEXT NOT NULL,
    learning_unit_id TEXT NOT NULL,
    mode TEXT NOT NULL,
    seen_at TEXT NOT NULL,
    PRIMARY KEY (user_id, learning_unit_id, mode)
);

CREATE TABLE IF NOT EXISTS user_profile (
    user_id TEXT PRIMARY KEY,
    display_name TEXT,
    avatar_url TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS app_session (
    session_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    access_token TEXT NOT NULL,
    refresh_token TEXT NOT NULL,
    csrf_token TEXT NOT NULL,
    display_name TEXT,
    email TEXT,
    phone TEXT,
    avatar_url TEXT,
    provider TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_progress_user
    ON learning_unit_progress(user_id);
CREATE INDEX IF NOT EXISTS idx_progress_user_next_revision
    ON learning_unit_progress(user_id, next_revision);
CREATE INDEX IF NOT EXISTS idx_progress_user_unit
    ON learning_unit_progress(user_id, learning_unit_id);
CREATE INDEX IF NOT EXISTS idx_modes_seen_user_unit
    ON unit_modes_seen(user_id, learning_unit_id);
CREATE INDEX IF NOT EXISTS idx_session_user
    ON app_session(user_id);

CREATE TABLE IF NOT EXISTS memory_entry (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
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
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    entry_id TEXT NOT NULL,
    storage_key TEXT NOT NULL,
    uploaded_at TEXT NOT NULL,
    UNIQUE(entry_id),
    FOREIGN KEY (entry_id) REFERENCES memory_entry(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_memory_user
    ON memory_entry(user_id);
CREATE INDEX IF NOT EXISTS idx_memory_user_created
    ON memory_entry(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_memory_user_next_revision
    ON memory_entry(user_id, next_revision);
CREATE INDEX IF NOT EXISTS idx_memory_media_user
    ON memory_media(user_id);
"""

_LEGACY_TABLES = (
    "learning_unit_progress",
    "split_preference",
    "article_gloss",
    "app_settings",
    "unit_modes_seen",
    "memory_entry",
    "memory_media",
)


def connect(db_path: Path | str) -> sqlite3.Connection:
    """Open a SQLite connection with row factory and foreign keys on."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
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


def _column_names(conn: sqlite3.Connection, table: str) -> list[str]:
    if not _table_exists(conn, table):
        return []
    return [str(row["name"]) for row in conn.execute(f"PRAGMA table_info({table})")]


def _pk_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    info = conn.execute(f"PRAGMA table_info({table})").fetchall()
    ranked = [(int(row["pk"]), str(row["name"])) for row in info if row["pk"]]
    ranked.sort()
    return [name for _pk, name in ranked]


def _has_unique_on(conn: sqlite3.Connection, table: str, columns: list[str]) -> bool:
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


def _legacy_schema(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='learning_unit_progress'"
    ).fetchone()
    if row is None or not row["sql"]:
        return False
    return "user_id" not in str(row["sql"])


def _migrate_legacy(conn: sqlite3.Connection) -> None:
    """One-time migrate pre-multiuser tables into user-scoped schema."""
    uid = str(LOCAL_USER_ID)
    conn.execute("PRAGMA foreign_keys = OFF")
    for name in _LEGACY_TABLES:
        if _table_exists(conn, name):
            conn.execute(f"ALTER TABLE {name} RENAME TO {name}_legacy")
    conn.executescript(SCHEMA_SQL)
    if _table_exists(conn, "learning_unit_progress_legacy"):
        conn.execute(
            f"""
            INSERT INTO learning_unit_progress (
                user_id, learning_unit_id, status, times_completed, last_completed,
                next_revision, interval_days, ease_factor, created_at, updated_at
            )
            SELECT '{uid}', learning_unit_id, status, times_completed, last_completed,
                   next_revision, interval_days, ease_factor, created_at, updated_at
            FROM learning_unit_progress_legacy
            """
        )
    if _table_exists(conn, "split_preference_legacy"):
        conn.execute(
            f"""
            INSERT INTO split_preference (user_id, parent_clause_id, mode, updated_at)
            SELECT '{uid}', parent_clause_id, mode, updated_at FROM split_preference_legacy
            """
        )
    if _table_exists(conn, "article_gloss_legacy"):
        conn.execute(
            f"""
            INSERT INTO article_gloss (user_id, article_number, text, updated_at)
            SELECT '{uid}', article_number, text, updated_at FROM article_gloss_legacy
            """
        )
    if _table_exists(conn, "app_settings_legacy"):
        conn.execute(
            f"""
            INSERT INTO app_settings (user_id, key, value, updated_at)
            SELECT '{uid}', key, value, updated_at FROM app_settings_legacy
            """
        )
    if _table_exists(conn, "unit_modes_seen_legacy"):
        conn.execute(
            f"""
            INSERT INTO unit_modes_seen (user_id, learning_unit_id, mode, seen_at)
            SELECT '{uid}', learning_unit_id, mode, seen_at FROM unit_modes_seen_legacy
            """
        )
    if _table_exists(conn, "memory_entry_legacy"):
        conn.execute(
            f"""
            INSERT INTO memory_entry (
                id, user_id, title, acronym, notes, logged_date, status, interval_days,
                last_completed, next_revision, times_completed, created_at, updated_at
            )
            SELECT id, '{uid}', title, acronym, notes, logged_date, status, interval_days,
                   last_completed, next_revision, times_completed, created_at, updated_at
            FROM memory_entry_legacy
            """
        )
    if _table_exists(conn, "memory_media_legacy"):
        cols = _column_names(conn, "memory_media_legacy")
        path_sql = "storage_key" if "storage_key" in cols else "path"
        if "path" in cols and "storage_key" in cols:
            path_sql = "COALESCE(NULLIF(storage_key, ''), path)"
        conn.execute(
            f"""
            INSERT INTO memory_media (id, user_id, entry_id, storage_key, uploaded_at)
            SELECT entry_id, '{uid}', entry_id, {path_sql}, uploaded_at
            FROM memory_media_legacy
            """
        )
    for name in _LEGACY_TABLES:
        conn.execute(f"DROP TABLE IF EXISTS {name}_legacy")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.commit()


def _rebuild_unit_modes_seen(conn: sqlite3.Connection) -> None:
    uid = str(LOCAL_USER_ID)
    cols = _column_names(conn, "unit_modes_seen")
    has_user = "user_id" in cols
    conn.execute("DROP INDEX IF EXISTS idx_modes_seen_unit")
    conn.execute("DROP INDEX IF EXISTS idx_modes_seen_user_unit")
    conn.execute(
        """
        CREATE TABLE unit_modes_seen_new (
            user_id TEXT NOT NULL,
            learning_unit_id TEXT NOT NULL,
            mode TEXT NOT NULL,
            seen_at TEXT NOT NULL,
            PRIMARY KEY (user_id, learning_unit_id, mode)
        )
        """
    )
    if has_user:
        conn.execute(
            """
            INSERT OR REPLACE INTO unit_modes_seen_new
                (user_id, learning_unit_id, mode, seen_at)
            SELECT user_id, learning_unit_id, mode, MAX(seen_at)
            FROM unit_modes_seen
            GROUP BY user_id, learning_unit_id, mode
            """
        )
    else:
        conn.execute(
            f"""
            INSERT OR REPLACE INTO unit_modes_seen_new
                (user_id, learning_unit_id, mode, seen_at)
            SELECT '{uid}', learning_unit_id, mode, MAX(seen_at)
            FROM unit_modes_seen
            GROUP BY learning_unit_id, mode
            """
        )
    conn.execute("DROP TABLE unit_modes_seen")
    conn.execute("ALTER TABLE unit_modes_seen_new RENAME TO unit_modes_seen")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_modes_seen_user_unit "
        "ON unit_modes_seen(user_id, learning_unit_id)"
    )


def _rebuild_app_settings(conn: sqlite3.Connection) -> None:
    uid = str(LOCAL_USER_ID)
    cols = _column_names(conn, "app_settings")
    has_user = "user_id" in cols
    conn.execute(
        """
        CREATE TABLE app_settings_new (
            user_id TEXT NOT NULL,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (user_id, key)
        )
        """
    )
    if has_user:
        conn.execute(
            """
            INSERT OR REPLACE INTO app_settings_new (user_id, key, value, updated_at)
            SELECT user_id, key, value, updated_at
            FROM app_settings
            WHERE rowid IN (
                SELECT MAX(rowid) FROM app_settings GROUP BY user_id, key
            )
            """
        )
    else:
        conn.execute(
            f"""
            INSERT OR REPLACE INTO app_settings_new (user_id, key, value, updated_at)
            SELECT '{uid}', key, value, updated_at
            FROM app_settings
            WHERE rowid IN (SELECT MAX(rowid) FROM app_settings GROUP BY key)
            """
        )
    conn.execute("DROP TABLE app_settings")
    conn.execute("ALTER TABLE app_settings_new RENAME TO app_settings")


def _repair_partial_legacy(conn: sqlite3.Connection) -> None:
    """Fix 8001 tables that exist without user_id or without a PRIMARY KEY.

    ``CREATE TABLE IF NOT EXISTS`` never alters those older shapes, so Done /
    mark_mode_seen upserts 500 until they match the user-scoped schema.
    """
    if _table_exists(conn, "unit_modes_seen") and (
        "user_id" not in _column_names(conn, "unit_modes_seen")
        or not _has_unique_on(
            conn, "unit_modes_seen", ["user_id", "learning_unit_id", "mode"]
        )
    ):
        _rebuild_unit_modes_seen(conn)
        logger.info("Rebuilt unit_modes_seen into user-scoped schema")
    if _table_exists(conn, "app_settings") and (
        "user_id" not in _column_names(conn, "app_settings")
        or not _has_unique_on(conn, "app_settings", ["user_id", "key"])
    ):
        _rebuild_app_settings(conn)
        logger.info("Rebuilt app_settings into user-scoped schema")


def init_db(conn: sqlite3.Connection) -> None:
    """Create progress tables if missing; migrate legacy single-user schema."""
    if _legacy_schema(conn):
        _migrate_legacy(conn)
        return
    conn.executescript(SCHEMA_SQL)
    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        _repair_partial_legacy(conn)
    finally:
        conn.execute("PRAGMA foreign_keys = ON")
    conn.commit()


def open_progress_db(db_path: Path | str) -> sqlite3.Connection:
    """Connect and ensure schema exists."""
    conn = connect(db_path)
    init_db(conn)
    return conn

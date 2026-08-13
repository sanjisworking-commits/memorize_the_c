"""SQLite connection and schema for learning progress (Sprint 3)."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

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


def _column_names(conn: sqlite3.Connection, table: str) -> list[str]:
    if not _table_exists(conn, table):
        return []
    return [str(row["name"]) for row in conn.execute(f"PRAGMA table_info({table})")]


def _has_column(conn: sqlite3.Connection, table: str, name: str) -> bool:
    return name in _column_names(conn, table)


def _rebuild_learning_unit_progress(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE learning_unit_progress_new (
            learning_unit_id TEXT PRIMARY KEY,
            status TEXT NOT NULL DEFAULT 'new',
            times_completed INTEGER NOT NULL DEFAULT 0,
            last_completed TEXT,
            next_revision TEXT,
            interval_days INTEGER NOT NULL DEFAULT 0,
            ease_factor REAL NOT NULL DEFAULT 2.5,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        INSERT OR REPLACE INTO learning_unit_progress_new (
            learning_unit_id, status, times_completed, last_completed,
            next_revision, interval_days, ease_factor, created_at, updated_at
        )
        SELECT learning_unit_id, status, times_completed, last_completed,
               next_revision, interval_days, ease_factor, created_at, updated_at
        FROM learning_unit_progress
        WHERE rowid IN (
            SELECT MAX(rowid) FROM learning_unit_progress GROUP BY learning_unit_id
        )
        """
    )
    conn.execute("DROP TABLE learning_unit_progress")
    conn.execute(
        "ALTER TABLE learning_unit_progress_new RENAME TO learning_unit_progress"
    )


def _rebuild_split_preference(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE split_preference_new (
            parent_clause_id TEXT PRIMARY KEY,
            mode TEXT NOT NULL CHECK (mode IN ('whole', 'letters')),
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        INSERT OR REPLACE INTO split_preference_new
            (parent_clause_id, mode, updated_at)
        SELECT parent_clause_id, mode, updated_at
        FROM split_preference
        WHERE rowid IN (
            SELECT MAX(rowid) FROM split_preference GROUP BY parent_clause_id
        )
        """
    )
    conn.execute("DROP TABLE split_preference")
    conn.execute("ALTER TABLE split_preference_new RENAME TO split_preference")


def _rebuild_article_gloss(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE article_gloss_new (
            article_number TEXT PRIMARY KEY,
            text TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        INSERT OR REPLACE INTO article_gloss_new (article_number, text, updated_at)
        SELECT article_number, text, updated_at
        FROM article_gloss
        WHERE rowid IN (
            SELECT MAX(rowid) FROM article_gloss GROUP BY article_number
        )
        """
    )
    conn.execute("DROP TABLE article_gloss")
    conn.execute("ALTER TABLE article_gloss_new RENAME TO article_gloss")


def _rebuild_memory_entry(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE memory_entry_new (
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
        )
        """
    )
    conn.execute(
        """
        INSERT OR REPLACE INTO memory_entry_new (
            id, title, acronym, notes, logged_date, status, interval_days,
            last_completed, next_revision, times_completed, created_at, updated_at
        )
        SELECT id, title, acronym, notes, logged_date, status, interval_days,
               last_completed, next_revision, times_completed, created_at, updated_at
        FROM memory_entry
        """
    )
    conn.execute("DROP TABLE memory_entry")
    conn.execute("ALTER TABLE memory_entry_new RENAME TO memory_entry")


def _rebuild_memory_media(conn: sqlite3.Connection) -> None:
    cols = _column_names(conn, "memory_media")
    path_sql = "path" if "path" in cols else "storage_key"
    if "path" in cols and "storage_key" in cols:
        path_sql = "COALESCE(NULLIF(path, ''), storage_key)"
    conn.execute(
        """
        CREATE TABLE memory_media_new (
            entry_id TEXT PRIMARY KEY,
            path TEXT NOT NULL,
            uploaded_at TEXT NOT NULL,
            FOREIGN KEY (entry_id) REFERENCES memory_entry(id) ON DELETE CASCADE
        )
        """
    )
    conn.execute(
        f"""
        INSERT OR REPLACE INTO memory_media_new (entry_id, path, uploaded_at)
        SELECT entry_id, {path_sql}, uploaded_at
        FROM memory_media
        WHERE rowid IN (
            SELECT MAX(rowid) FROM memory_media GROUP BY entry_id
        )
        """
    )
    conn.execute("DROP TABLE memory_media")
    conn.execute("ALTER TABLE memory_media_new RENAME TO memory_media")


def _strip_multiuser_user_id(conn: sqlite3.Connection) -> bool:
    """Rebuild 8001 tables if a multi-user process added ``user_id``.

    ``CREATE TABLE IF NOT EXISTS`` never removes columns. main's Done insert
    omits ``user_id``, so a migrated local DB 500s with NOT NULL user_id.
    Rows are kept; duplicate unit keys keep the latest rowid.
    """
    progress = _table_exists(conn, "learning_unit_progress") and _has_column(
        conn, "learning_unit_progress", "user_id"
    )
    split = _table_exists(conn, "split_preference") and _has_column(
        conn, "split_preference", "user_id"
    )
    gloss = _table_exists(conn, "article_gloss") and _has_column(
        conn, "article_gloss", "user_id"
    )
    settings = _table_exists(conn, "app_settings") and _has_column(
        conn, "app_settings", "user_id"
    )
    modes = _table_exists(conn, "unit_modes_seen") and _has_column(
        conn, "unit_modes_seen", "user_id"
    )
    memory = _table_exists(conn, "memory_entry") and _has_column(
        conn, "memory_entry", "user_id"
    )
    media = _table_exists(conn, "memory_media") and (
        _has_column(conn, "memory_media", "user_id")
        or _has_column(conn, "memory_media", "storage_key")
    )
    if not any((progress, split, gloss, settings, modes, memory, media)):
        return False

    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        if progress:
            _rebuild_learning_unit_progress(conn)
        if split:
            _rebuild_split_preference(conn)
        if gloss:
            _rebuild_article_gloss(conn)
        if settings:
            _rebuild_app_settings(conn)
        if modes:
            _rebuild_unit_modes_seen(conn)
        if memory:
            _rebuild_memory_entry(conn)
        if media:
            _rebuild_memory_media(conn)
    finally:
        conn.execute("PRAGMA foreign_keys = ON")
    logger.info("Stripped multi-user user_id columns from local progress.db")
    return True


def migrate_schema(conn: sqlite3.Connection) -> None:
    """Upgrade older local progress.db files in place.

    ``CREATE TABLE IF NOT EXISTS`` does not alter existing tables. Two cases
    500 Learn/Done on 8001:

    * ``unit_modes_seen`` / ``app_settings`` created without PRIMARY KEYs
    * tables opened by multi-user code, which adds a NOT NULL ``user_id``
    """
    _strip_multiuser_user_id(conn)
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
    conn.executescript(SCHEMA_SQL)
    conn.commit()


def open_progress_db(db_path: Path | str) -> sqlite3.Connection:
    """Connect and ensure schema exists."""
    conn = connect(db_path)
    init_db(conn)
    return conn

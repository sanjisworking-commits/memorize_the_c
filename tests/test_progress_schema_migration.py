"""Upgrade older local progress.db tables that lack PRIMARY KEYs."""

from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

from constitution_memorizer.learning.schemas import LearningUnit, LearningUnitType
from constitution_memorizer.progress.db import open_progress_db
from constitution_memorizer.progress.repository import ProgressRepository
from constitution_memorizer.progress.scheduler import ReminderEngine


def _legacy_modes_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE unit_modes_seen (
            learning_unit_id TEXT NOT NULL,
            mode TEXT NOT NULL,
            seen_at TEXT NOT NULL
        );
        CREATE TABLE app_settings (
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        INSERT INTO unit_modes_seen VALUES
            ('article-138-clause-2', 'read', '2026-08-05T05:57:54+00:00'),
            ('article-38-clause-1', 'read', '2026-08-07T03:51:57+00:00');
        INSERT INTO app_settings VALUES
            ('theme', 'light', '2026-08-01T00:00:00+00:00'),
            ('theme', 'light', '2026-08-02T00:00:00+00:00');
        """
    )
    conn.commit()
    conn.close()


def test_open_upgrades_legacy_modes_seen_and_settings(tmp_path: Path):
    db = tmp_path / "progress.db"
    _legacy_modes_db(db)

    conn = open_progress_db(db)
    modes_sql = conn.execute(
        "SELECT sql FROM sqlite_master WHERE name = 'unit_modes_seen'"
    ).fetchone()[0]
    assert "PRIMARY KEY" in modes_sql
    settings_sql = conn.execute(
        "SELECT sql FROM sqlite_master WHERE name = 'app_settings'"
    ).fetchone()[0]
    assert "PRIMARY KEY" in settings_sql

    rows = conn.execute(
        "SELECT learning_unit_id, mode FROM unit_modes_seen ORDER BY 1, 2"
    ).fetchall()
    assert [tuple(r) for r in rows] == [
        ("article-138-clause-2", "read"),
        ("article-38-clause-1", "read"),
    ]
    themes = conn.execute(
        "SELECT COUNT(*) FROM app_settings WHERE key = 'theme'"
    ).fetchone()[0]
    assert themes == 1

    repo = ProgressRepository(conn)
    seen = repo.mark_mode_seen("article-138-clause-2", "read")
    assert "read" in seen
    seen = repo.mark_mode_seen("article-138-clause-2", "cloze")
    assert seen == {"read", "cloze"}
    repo.set_setting("theme", "dark")
    assert repo.get_setting("theme") == "dark"


def test_fresh_db_mark_mode_seen_is_idempotent(tmp_path: Path):
    repo = ProgressRepository(open_progress_db(tmp_path / "fresh.db"))
    assert repo.mark_mode_seen("article-2", "read") == {"read"}
    assert repo.mark_mode_seen("article-2", "read") == {"read"}


def _multiuser_progress_db(path: Path) -> None:
    """Shape produced when feature/multiuser-auth opens a local progress.db."""
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE learning_unit_progress (
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
        CREATE TABLE unit_modes_seen (
            user_id TEXT NOT NULL,
            learning_unit_id TEXT NOT NULL,
            mode TEXT NOT NULL,
            seen_at TEXT NOT NULL,
            PRIMARY KEY (user_id, learning_unit_id, mode)
        );
        CREATE TABLE app_settings (
            user_id TEXT NOT NULL,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (user_id, key)
        );
        CREATE TABLE split_preference (
            user_id TEXT NOT NULL,
            parent_clause_id TEXT NOT NULL,
            mode TEXT NOT NULL CHECK (mode IN ('whole', 'letters')),
            updated_at TEXT NOT NULL,
            PRIMARY KEY (user_id, parent_clause_id)
        );
        CREATE TABLE article_gloss (
            user_id TEXT NOT NULL,
            article_number TEXT NOT NULL,
            text TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (user_id, article_number)
        );
        CREATE TABLE memory_entry (
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
        CREATE TABLE memory_media (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            entry_id TEXT NOT NULL,
            storage_key TEXT NOT NULL,
            uploaded_at TEXT NOT NULL
        );
        INSERT INTO learning_unit_progress VALUES
            ('00000000-0000-4000-8000-000000000001', 'article-1-clause-1',
             'review', 1, '2026-08-08', '2026-08-09', 1, 2.5,
             '2026-08-08T00:00:00+00:00', '2026-08-08T00:00:00+00:00');
        INSERT INTO unit_modes_seen VALUES
            ('00000000-0000-4000-8000-000000000001', 'article-1-clause-1',
             'read', '2026-08-08T00:00:00+00:00');
        INSERT INTO app_settings VALUES
            ('00000000-0000-4000-8000-000000000001', 'theme', 'light',
             '2026-08-08T00:00:00+00:00');
        INSERT INTO split_preference VALUES
            ('00000000-0000-4000-8000-000000000001', 'article-19-clause-1',
             'letters', '2026-08-08T00:00:00+00:00');
        INSERT INTO article_gloss VALUES
            ('00000000-0000-4000-8000-000000000001', '1', 'notes',
             '2026-08-08T00:00:00+00:00');
        INSERT INTO memory_entry VALUES
            ('mem-abc', '00000000-0000-4000-8000-000000000001',
             'Preamble', '', '', '2026-08-08', 'review', 1, NULL,
             '2026-08-09', 0, '2026-08-08T00:00:00+00:00',
             '2026-08-08T00:00:00+00:00');
        INSERT INTO memory_media VALUES
            ('media-1', '00000000-0000-4000-8000-000000000001',
             'mem-abc', 'memory/mem-abc.jpg', '2026-08-08T00:00:00+00:00');
        """
    )
    conn.commit()
    conn.close()


def test_open_strips_multiuser_user_id_and_done_inserts(tmp_path: Path):
    db = tmp_path / "progress.db"
    _multiuser_progress_db(db)

    conn = open_progress_db(db)
    progress_cols = [
        row["name"]
        for row in conn.execute("PRAGMA table_info(learning_unit_progress)")
    ]
    assert "user_id" not in progress_cols
    modes_cols = [
        row["name"] for row in conn.execute("PRAGMA table_info(unit_modes_seen)")
    ]
    assert "user_id" not in modes_cols
    media_cols = [
        row["name"] for row in conn.execute("PRAGMA table_info(memory_media)")
    ]
    assert "storage_key" not in media_cols
    assert "path" in media_cols

    kept = conn.execute(
        """
        SELECT status, times_completed, next_revision
        FROM learning_unit_progress
        WHERE learning_unit_id = 'article-1-clause-1'
        """
    ).fetchone()
    assert kept is not None
    assert kept["status"] == "review"
    assert kept["times_completed"] == 1
    assert kept["next_revision"] == "2026-08-09"
    assert conn.execute(
        "SELECT mode FROM split_preference WHERE parent_clause_id = 'article-19-clause-1'"
    ).fetchone()[0] == "letters"
    assert conn.execute(
        "SELECT text FROM article_gloss WHERE article_number = '1'"
    ).fetchone()[0] == "notes"
    assert conn.execute(
        "SELECT path FROM memory_media WHERE entry_id = 'mem-abc'"
    ).fetchone()[0] == "memory/mem-abc.jpg"

    repo = ProgressRepository(conn)
    created = repo.ensure_progress("article-2")
    assert created.learning_unit_id == "article-2"
    assert created.status == "new"
    seen = repo.mark_mode_seen("article-1-clause-1", "cloze")
    assert seen == {"read", "cloze"}
    repo.set_setting("theme", "dark")
    assert repo.get_setting("theme") == "dark"


def test_open_strips_duplicate_user_rows_keeps_one(tmp_path: Path):
    db = tmp_path / "progress.db"
    conn = sqlite3.connect(db)
    conn.executescript(
        """
        CREATE TABLE learning_unit_progress (
            user_id TEXT NOT NULL,
            learning_unit_id TEXT NOT NULL,
            status TEXT NOT NULL,
            times_completed INTEGER NOT NULL,
            last_completed TEXT,
            next_revision TEXT,
            interval_days INTEGER NOT NULL,
            ease_factor REAL NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (user_id, learning_unit_id)
        );
        INSERT INTO learning_unit_progress VALUES
            ('user-a', 'article-2', 'review', 1, '2026-08-01', '2026-08-02',
             1, 2.5, '2026-08-01T00:00:00+00:00', '2026-08-01T00:00:00+00:00'),
            ('user-b', 'article-2', 'review', 3, '2026-08-10', '2026-08-11',
             3, 2.5, '2026-08-10T00:00:00+00:00', '2026-08-10T00:00:00+00:00');
        """
    )
    conn.commit()
    conn.close()

    opened = open_progress_db(db)
    rows = opened.execute(
        "SELECT times_completed FROM learning_unit_progress WHERE learning_unit_id = 'article-2'"
    ).fetchall()
    assert len(rows) == 1
    assert rows[0]["times_completed"] == 3


def test_mark_done_after_multiuser_schema_strip(tmp_path: Path):
    db = tmp_path / "progress.db"
    _multiuser_progress_db(db)
    unit = LearningUnit(
        id="article-2",
        type=LearningUnitType.ARTICLE,
        display_title="Article 2",
        text="Name and territory of the Union.",
        estimated_learning_time=30,
        revision_order=1,
    )
    engine = ReminderEngine.from_units(db, [unit])
    engine.mark_all_modes_seen("article-2")
    result = engine.mark_done("article-2", as_of=date(2026, 8, 13))
    assert result.progress.status == "review"
    assert result.progress.times_completed == 1

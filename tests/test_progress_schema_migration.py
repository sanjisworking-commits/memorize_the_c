"""Upgrade older local progress.db tables that lack PRIMARY KEYs."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from constitution_memorizer.progress.db import open_progress_db
from constitution_memorizer.progress.repository import ProgressRepository


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

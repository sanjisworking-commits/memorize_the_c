"""Access-grant store matrix: effective grant, overlap rule, role bit."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from constitution_memorizer.admin.repository import SqliteAdminRepository
from constitution_memorizer.admin.store import AccessOverride, SqliteAccessStore
from constitution_memorizer.progress.db import open_progress_db

NOW = datetime(2026, 8, 18, 12, 0, 0, tzinfo=timezone.utc)
USER = str(uuid4())
ADMIN = str(uuid4())


@pytest.fixture()
def conn(tmp_path: Path):
    connection = open_progress_db(tmp_path / "progress.db")
    yield connection
    connection.close()


@pytest.fixture()
def store(conn) -> SqliteAccessStore:
    return SqliteAccessStore(conn)


def _iso(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat()


def _insert_grant(
    conn,
    *,
    user_id: str = USER,
    source: str = "admin_grant",
    starts_at: datetime = NOW - timedelta(days=1),
    ends_at: datetime | None = None,
    revoked_at: datetime | None = None,
) -> str:
    grant_id = str(uuid4())
    conn.execute(
        """
        INSERT INTO access_grants (
            id, user_id, source, starts_at, ends_at, reason,
            granted_by, created_at, revoked_at
        ) VALUES (?, ?, ?, ?, ?, 'test', ?, ?, ?)
        """,
        (
            grant_id,
            user_id,
            source,
            _iso(starts_at),
            _iso(ends_at) if ends_at else None,
            ADMIN,
            _iso(NOW),
            _iso(revoked_at) if revoked_at else None,
        ),
    )
    conn.commit()
    return grant_id


def _make_admin(conn, user_id: str = USER) -> None:
    conn.execute(
        "INSERT INTO user_roles (user_id, role, created_at) VALUES (?, 'admin', ?)",
        (user_id, _iso(NOW)),
    )
    conn.commit()


class TestEffectiveGrant:
    def test_no_grant(self, store):
        override = store.resolve_access_override(USER, NOW)
        assert override == AccessOverride()
        assert not override.has_recall_access

    def test_active_indefinite(self, conn, store):
        grant_id = _insert_grant(conn, ends_at=None)
        override = store.resolve_access_override(USER, NOW)
        assert override.effective_grant is not None
        assert override.effective_grant.grant_id == grant_id
        assert override.effective_grant.ends_at is None
        assert override.has_recall_access
        assert not override.is_admin

    def test_future_starts_at_not_active(self, conn, store):
        _insert_grant(conn, starts_at=NOW + timedelta(days=1))
        assert store.resolve_access_override(USER, NOW).effective_grant is None

    def test_expired_ends_at_not_active(self, conn, store):
        _insert_grant(conn, ends_at=NOW - timedelta(minutes=1))
        assert store.resolve_access_override(USER, NOW).effective_grant is None

    def test_revoked_wins_over_future_ends_at(self, conn, store):
        _insert_grant(
            conn,
            ends_at=NOW + timedelta(days=30),
            revoked_at=NOW - timedelta(hours=1),
        )
        assert store.resolve_access_override(USER, NOW).effective_grant is None

    def test_overlap_furthest_ends_at_wins(self, conn, store):
        _insert_grant(conn, ends_at=NOW + timedelta(days=7))
        winner = _insert_grant(conn, ends_at=NOW + timedelta(days=30))
        grant = store.resolve_access_override(USER, NOW).effective_grant
        assert grant is not None and grant.grant_id == winner

    def test_overlap_indefinite_beats_dated(self, conn, store):
        _insert_grant(conn, ends_at=NOW + timedelta(days=365))
        winner = _insert_grant(conn, ends_at=None)
        grant = store.resolve_access_override(USER, NOW).effective_grant
        assert grant is not None and grant.grant_id == winner
        assert grant.ends_at is None

    def test_other_users_grant_is_invisible(self, conn, store):
        _insert_grant(conn, user_id=str(uuid4()))
        assert not store.resolve_access_override(USER, NOW).has_recall_access

    def test_promotion_source_carried(self, conn, store):
        _insert_grant(conn, source="promotion")
        grant = store.resolve_access_override(USER, NOW).effective_grant
        assert grant is not None and grant.source == "promotion"


class TestAdminBit:
    def test_is_admin(self, conn, store):
        assert not store.is_admin(USER)
        _make_admin(conn)
        assert store.is_admin(USER)

    def test_override_carries_admin_without_grant(self, conn, store):
        _make_admin(conn)
        override = store.resolve_access_override(USER, NOW)
        assert override.is_admin
        assert override.effective_grant is None
        assert override.has_recall_access

    def test_admin_plus_grant(self, conn, store):
        _make_admin(conn)
        _insert_grant(conn, ends_at=NOW + timedelta(days=5))
        override = store.resolve_access_override(USER, NOW)
        assert override.is_admin
        assert override.effective_grant is not None


class TestGrantRowState:
    def test_states_derived_from_timestamps(self, conn):
        repo = SqliteAdminRepository(conn)
        active = _insert_grant(conn, ends_at=NOW + timedelta(days=5))
        scheduled = _insert_grant(conn, starts_at=NOW + timedelta(days=2))
        ended = _insert_grant(conn, ends_at=NOW - timedelta(days=1))
        revoked = _insert_grant(conn, revoked_at=NOW - timedelta(hours=2))
        states = {g.id: g.state(NOW) for g in repo.list_grants(USER, limit=10)}
        assert states[active] == "active"
        assert states[scheduled] == "scheduled"
        assert states[ended] == "ended"
        assert states[revoked] == "revoked"


class TestSchemaShape:
    """Tripwire: the two DDL sources must agree on the admin tables."""

    TABLES = ("user_roles", "access_grants", "admin_audit_log")
    PROFILE_COLUMNS = ("email", "phone", "last_sign_in_at")

    def test_sqlite_ddl_has_admin_tables_and_identity_columns(self, conn):
        names = {
            r["name"]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        for table in self.TABLES:
            assert table in names
        profile_cols = {
            r["name"] for r in conn.execute("PRAGMA table_info(user_profile)")
        }
        for column in self.PROFILE_COLUMNS:
            assert column in profile_cols

    def test_alembic_ddl_has_admin_tables_and_identity_columns(self):
        root = Path(__file__).resolve().parents[1]
        sql = (
            root
            / "alembic"
            / "versions"
            / "20260818_0006_admin_roles_grants_audit.py"
        ).read_text(encoding="utf-8")
        for table in self.TABLES:
            assert f"CREATE TABLE IF NOT EXISTS {table}" in sql
        for column in self.PROFILE_COLUMNS:
            assert f"ADD COLUMN IF NOT EXISTS {column}" in sql

    def test_existing_sqlite_db_gains_identity_columns(self, tmp_path):
        # A pre-0006 DB (user_profile without the identity columns) must be
        # upgraded in place by init_db.
        import sqlite3

        path = tmp_path / "old.db"
        conn = sqlite3.connect(path)
        conn.execute(
            """
            CREATE TABLE user_profile (
                user_id TEXT PRIMARY KEY,
                display_name TEXT,
                avatar_url TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "INSERT INTO user_profile VALUES ('u1', 'Name', NULL, 't', 't')"
        )
        conn.commit()
        conn.close()
        upgraded = open_progress_db(path)
        cols = {
            r["name"] for r in upgraded.execute("PRAGMA table_info(user_profile)")
        }
        assert {"email", "phone", "last_sign_in_at"} <= cols
        row = upgraded.execute(
            "SELECT display_name, email FROM user_profile WHERE user_id = 'u1'"
        ).fetchone()
        assert row["display_name"] == "Name" and row["email"] is None
        upgraded.close()

"""Process-local L1 cache on PostgresSessionStore (hit/miss, TTL, epoch race)."""

from __future__ import annotations

import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from uuid import UUID

from constitution_memorizer.auth.models import AuthenticatedUser
from constitution_memorizer.auth.sessions import (
    PostgresSessionStore,
    StoredSession,
    _SessionL1Cache,
)

USER_ID = UUID("11111111-1111-4111-8111-111111111111")
NOW = datetime(2026, 8, 15, 12, 0, tzinfo=timezone.utc)
SID = "session-abc"


class FakeClock:
    def __init__(self, start: float = 100.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class _FakeResult:
    def __init__(self, row: object) -> None:
        self._row = row

    def fetchone(self):
        return self._row


class SessionFakePool:
    """In-memory app_session stand-in that counts SQL and can pause SELECT."""

    def __init__(self) -> None:
        self.rows: dict[str, tuple | None] = {}
        self.selects = 0
        self.inserts = 0
        self.deletes = 0
        self.updates = 0
        self.select_started = threading.Event()
        self.allow_select = threading.Event()
        self.allow_select.set()
        self.pause_selects = False

    def seed(self, row: tuple) -> None:
        self.rows[row[0]] = row

    @contextmanager
    def connection(self):
        pool = self

        class _Conn:
            def execute(self, sql, params=None):
                kind = sql.strip().split(None, 1)[0].upper()
                if kind == "SELECT":
                    pool.selects += 1
                    session_id = params[0]
                    row = pool.rows.get(session_id)
                    if pool.pause_selects:
                        pool.select_started.set()
                        pool.allow_select.wait(timeout=5)
                    return _FakeResult(row)
                if kind == "INSERT":
                    pool.inserts += 1
                    pool.rows[params[0]] = tuple(params)
                    return _FakeResult(None)
                if kind == "DELETE":
                    pool.deletes += 1
                    pool.rows.pop(params[0], None)
                    return _FakeResult(None)
                if kind == "UPDATE":
                    pool.updates += 1
                    session_id = params[3]
                    existing = pool.rows.get(session_id)
                    if existing is not None:
                        pool.rows[session_id] = (
                            existing[0],
                            existing[1],
                            params[0],
                            params[1],
                            existing[4],
                            existing[5],
                            existing[6],
                            existing[7],
                            existing[8],
                            existing[9],
                            params[2],
                            existing[11],
                        )
                    return _FakeResult(None)
                raise AssertionError(f"unexpected SQL: {sql}")

            def commit(self) -> None:
                return None

        yield _Conn()


def _user() -> AuthenticatedUser:
    return AuthenticatedUser(
        id=USER_ID,
        email="ada@example.com",
        phone=None,
        display_name="Ada",
        avatar_url=None,
        provider="google",
    )


def _row(
    session_id: str = SID,
    *,
    access_token: str = "access-token",
    refresh_token: str = "refresh-token",
    expires_at: datetime | None = None,
) -> tuple:
    created = NOW
    return (
        session_id,
        str(USER_ID),
        access_token,
        refresh_token,
        "csrf-token",
        "Ada",
        "ada@example.com",
        None,
        None,
        "google",
        expires_at if expires_at is not None else NOW + timedelta(days=1),
        created,
    )


def _store(pool: SessionFakePool, **l1_kwargs) -> PostgresSessionStore:
    clock = l1_kwargs.pop("clock", FakeClock())
    return PostgresSessionStore(
        pool,
        l1=_SessionL1Cache(
            ttl_seconds=l1_kwargs.pop("ttl_seconds", 1),
            max_entries=l1_kwargs.pop("max_entries", 3),
            clock=clock,
            **l1_kwargs,
        ),
    )


def _session(
    session_id: str,
    *,
    expires_at: datetime | None = None,
    access_token: str = "access-token",
) -> StoredSession:
    return StoredSession(
        session_id=session_id,
        user=_user(),
        access_token=access_token,
        refresh_token="refresh-token",
        csrf_token="csrf-token",
        expires_at=expires_at if expires_at is not None else NOW + timedelta(days=1),
        created_at=NOW,
    )


def test_get_miss_then_hit_skips_second_select():
    pool = SessionFakePool()
    pool.seed(_row())
    store = _store(pool)

    first = store.get(SID)
    assert first is not None
    assert first.session_id == SID
    assert first.user.email == "ada@example.com"
    assert pool.selects == 1

    second = store.get(SID)
    assert second is not None
    assert second.session_id == SID
    assert second.user.email == "ada@example.com"
    assert second.access_token == "access-token"
    assert pool.selects == 1


def test_l1_ttl_expiry_hits_postgres_again():
    pool = SessionFakePool()
    pool.seed(_row())
    clock = FakeClock()
    store = _store(pool, clock=clock, ttl_seconds=1)

    assert store.get(SID) is not None
    assert pool.selects == 1

    clock.advance(0.5)
    assert store.get(SID) is not None
    assert pool.selects == 1

    clock.advance(0.6)
    assert store.get(SID) is not None
    assert pool.selects == 2


def test_expired_db_row_is_deleted_and_not_cached():
    pool = SessionFakePool()
    pool.seed(_row(expires_at=NOW - timedelta(minutes=1)))
    store = _store(pool)

    assert store.get(SID) is None
    assert pool.deletes == 1
    assert store._l1.contains(SID) is False
    assert store.get(SID) is None
    assert pool.selects == 2


def test_create_primes_l1_so_get_does_not_select():
    pool = SessionFakePool()
    store = _store(pool)

    created = store.create(_user(), access_token="a1", refresh_token="r1")
    assert pool.inserts == 1
    assert pool.selects == 0

    loaded = store.get(created.session_id)
    assert loaded is not None
    assert loaded.access_token == "a1"
    assert pool.selects == 0


def test_delete_evicts_so_later_get_misses():
    pool = SessionFakePool()
    pool.seed(_row())
    store = _store(pool)

    assert store.get(SID) is not None
    assert pool.selects == 1

    store.delete(SID)
    assert pool.deletes == 1
    assert store._l1.contains(SID) is False

    assert store.get(SID) is None
    assert pool.selects == 2


def test_touch_invalidates_then_refreshes_tokens():
    pool = SessionFakePool()
    pool.seed(_row())
    store = _store(pool)

    cached = store.get(SID)
    assert cached is not None
    assert cached.access_token == "access-token"
    assert pool.selects == 1

    updated = store.touch(SID, access_token="new-access", refresh_token="new-refresh")
    assert updated is not None
    assert updated.access_token == "new-access"
    assert updated.refresh_token == "new-refresh"
    assert pool.updates == 1
    assert pool.selects == 2

    again = store.get(SID)
    assert again is not None
    assert again.access_token == "new-access"
    assert pool.selects == 2


def test_lru_evicts_oldest_when_over_max_entries():
    cache = _SessionL1Cache(ttl_seconds=1, max_entries=3, clock=FakeClock())
    cache.put(_session("s1"))
    cache.put(_session("s2"))
    cache.put(_session("s3"))
    cache.put(_session("s4"))

    assert cache.contains("s1") is False
    assert cache.contains("s2") is True
    assert cache.contains("s3") is True
    assert cache.contains("s4") is True

    pool = SessionFakePool()
    pool.seed(_row("s1"))
    pool.seed(_row("s2"))
    pool.seed(_row("s3"))
    pool.seed(_row("s4"))
    store = PostgresSessionStore(pool, l1=cache)
    assert store.get("s1") is not None
    assert pool.selects == 1
    assert store.get("s4") is not None
    assert pool.selects == 1


def test_unknown_id_is_not_negative_cached():
    pool = SessionFakePool()
    store = _store(pool)

    assert store.get("missing") is None
    assert store._l1.contains("missing") is False
    assert pool.selects == 1

    assert store.get("missing") is None
    assert pool.selects == 2


def test_expired_cached_session_is_not_served():
    pool = SessionFakePool()
    pool.seed(_row(expires_at=NOW - timedelta(seconds=1)))
    store = _store(pool)
    store._l1.put(_session(SID, expires_at=NOW + timedelta(days=1)))
    cached = store._l1.lookup_or_epoch(SID)[0]
    assert cached is not None
    cached.expires_at = NOW - timedelta(seconds=1)

    assert store.get(SID) is None
    assert store._l1.contains(SID) is False
    assert pool.deletes == 1


def test_in_flight_select_cannot_repopulate_after_delete():
    pool = SessionFakePool()
    pool.seed(_row())
    store = _store(pool)
    pool.pause_selects = True
    pool.allow_select.clear()

    result: list[StoredSession | None] = []

    def _blocked_get() -> None:
        result.append(store.get(SID))

    worker = threading.Thread(target=_blocked_get)
    worker.start()
    assert pool.select_started.wait(timeout=5)

    store.delete(SID)
    pool.allow_select.set()
    worker.join(timeout=5)
    assert worker.is_alive() is False

    assert store._l1.contains(SID) is False
    assert store.get(SID) is None
    assert pool.deletes >= 1

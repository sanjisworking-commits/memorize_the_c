"""Server-side session store (in-memory and PostgreSQL)."""

from __future__ import annotations

import secrets
import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol
from uuid import UUID

from constitution_memorizer.auth.exceptions import SessionExpiredError
from constitution_memorizer.auth.models import AuthenticatedUser

SESSION_COOKIE_NAME = "rtc_session"
CSRF_COOKIE_NAME = "rtc_csrf"
SESSION_TTL = timedelta(days=14)
SESSION_L1_TTL = 30
SESSION_L1_MAX = 1024


@dataclass
class StoredSession:
    session_id: str
    user: AuthenticatedUser
    access_token: str
    refresh_token: str
    csrf_token: str
    expires_at: datetime
    created_at: datetime


class SessionStore(Protocol):
    def create(
        self,
        user: AuthenticatedUser,
        *,
        access_token: str,
        refresh_token: str,
    ) -> StoredSession:
        ...

    def get(self, session_id: str) -> StoredSession | None:
        ...

    def delete(self, session_id: str) -> None:
        ...

    def touch(self, session_id: str, *, access_token: str, refresh_token: str) -> StoredSession | None:
        ...


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


class _SessionL1Cache:
    """Process-local LRU for Postgres sessions. Never hold the lock during I/O."""

    def __init__(
        self,
        ttl_seconds: float = SESSION_L1_TTL,
        max_entries: int = SESSION_L1_MAX,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._ttl_seconds = ttl_seconds
        self._max_entries = max_entries
        self._clock = clock
        self._lock = threading.Lock()
        self._epoch = 0
        self._entries: OrderedDict[str, tuple[StoredSession, float]] = OrderedDict()

    def lookup_or_epoch(self, session_id: str) -> tuple[StoredSession | None, int]:
        """Return a fresh L1 hit, or (None, epoch) to load from PostgreSQL."""
        with self._lock:
            session = self._lookup_unlocked(session_id)
            if session is not None and _as_utc(session.expires_at) <= _now():
                self._evict_unlocked(session_id)
                session = None
            return session, self._epoch

    def put(self, session: StoredSession) -> None:
        with self._lock:
            self._put_unlocked(session)

    def put_if_epoch(self, session: StoredSession, epoch: int) -> bool:
        with self._lock:
            if self._epoch != epoch:
                return False
            self._put_unlocked(session)
            return True

    def invalidate(self, session_id: str) -> None:
        with self._lock:
            self._epoch += 1
            self._evict_unlocked(session_id)

    def contains(self, session_id: str) -> bool:
        with self._lock:
            return session_id in self._entries

    def _lookup_unlocked(self, session_id: str) -> StoredSession | None:
        entry = self._entries.get(session_id)
        if entry is None:
            return None
        session, deadline = entry
        if self._clock() >= deadline:
            self._evict_unlocked(session_id)
            return None
        self._entries.move_to_end(session_id)
        return session

    def _put_unlocked(self, session: StoredSession) -> None:
        if _as_utc(session.expires_at) <= _now():
            return
        self._entries[session.session_id] = (
            session,
            self._clock() + self._ttl_seconds,
        )
        self._entries.move_to_end(session.session_id)
        while len(self._entries) > self._max_entries:
            self._entries.popitem(last=False)

    def _evict_unlocked(self, session_id: str) -> None:
        self._entries.pop(session_id, None)


def new_session_id() -> str:
    return secrets.token_urlsafe(32)


def new_csrf_token() -> str:
    return secrets.token_urlsafe(24)


class InMemorySessionStore:
    """Process-local session store for tests and local multi-user without Postgres sessions."""

    def __init__(self) -> None:
        self._sessions: dict[str, StoredSession] = {}

    def create(
        self,
        user: AuthenticatedUser,
        *,
        access_token: str,
        refresh_token: str,
    ) -> StoredSession:
        now = _now()
        session = StoredSession(
            session_id=new_session_id(),
            user=user,
            access_token=access_token,
            refresh_token=refresh_token,
            csrf_token=new_csrf_token(),
            expires_at=now + SESSION_TTL,
            created_at=now,
        )
        self._sessions[session.session_id] = session
        return session

    def get(self, session_id: str) -> StoredSession | None:
        session = self._sessions.get(session_id)
        if session is None:
            return None
        if session.expires_at <= _now():
            self.delete(session_id)
            return None
        return session

    def delete(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    def touch(
        self,
        session_id: str,
        *,
        access_token: str,
        refresh_token: str,
    ) -> StoredSession | None:
        session = self.get(session_id)
        if session is None:
            return None
        updated = StoredSession(
            session_id=session.session_id,
            user=session.user,
            access_token=access_token,
            refresh_token=refresh_token,
            csrf_token=session.csrf_token,
            expires_at=_now() + SESSION_TTL,
            created_at=session.created_at,
        )
        self._sessions[session_id] = updated
        return updated


class PostgresSessionStore:
    """Persist sessions in PostgreSQL ``app_session``.

    PostgreSQL remains the persistent source of truth; the process-local L1 may
    intentionally serve a valid cached session for at most 30 seconds.

    Each application replica has its own L1. A logout handled by replica A
    cannot evict replica B's memory, so cross-instance revocation has a
    maximum ~30-second staleness window. Instant global revocation would need
    a shared cache or revocation list — not this process-local layer.
    """

    def __init__(self, pool, *, l1: _SessionL1Cache | None = None) -> None:
        self._pool = pool
        self._l1 = l1 or _SessionL1Cache()

    def create(
        self,
        user: AuthenticatedUser,
        *,
        access_token: str,
        refresh_token: str,
    ) -> StoredSession:
        now = _now()
        session = StoredSession(
            session_id=new_session_id(),
            user=user,
            access_token=access_token,
            refresh_token=refresh_token,
            csrf_token=new_csrf_token(),
            expires_at=now + SESSION_TTL,
            created_at=now,
        )
        with self._pool.connection() as conn:
            conn.execute(
                """
                INSERT INTO app_session (
                    session_id, user_id, access_token, refresh_token, csrf_token,
                    display_name, email, phone, avatar_url, provider,
                    expires_at, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    session.session_id,
                    str(user.id),
                    access_token,
                    refresh_token,
                    session.csrf_token,
                    user.display_name,
                    user.email,
                    user.phone,
                    user.avatar_url,
                    user.provider,
                    session.expires_at,
                    session.created_at,
                ),
            )
            conn.commit()
        self._l1.put(session)
        return session

    def get(self, session_id: str) -> StoredSession | None:
        cached, start_epoch = self._l1.lookup_or_epoch(session_id)
        if cached is not None:
            return cached
        with self._pool.connection() as conn:
            row = conn.execute(
                """
                SELECT session_id, user_id, access_token, refresh_token, csrf_token,
                       display_name, email, phone, avatar_url, provider,
                       expires_at, created_at
                FROM app_session
                WHERE session_id = %s
                """,
                (session_id,),
            ).fetchone()
        if row is None:
            return None
        expires_at = _as_utc(row[10])
        if expires_at <= _now():
            self.delete(session_id)
            return None
        user = AuthenticatedUser(
            id=UUID(str(row[1])),
            email=row[6],
            phone=row[7],
            display_name=row[5],
            avatar_url=row[8],
            provider=row[9],
        )
        created = _as_utc(row[11])
        session = StoredSession(
            session_id=row[0],
            user=user,
            access_token=row[2],
            refresh_token=row[3],
            csrf_token=row[4],
            expires_at=expires_at,
            created_at=created,
        )
        self._l1.put_if_epoch(session, start_epoch)
        return session

    def delete(self, session_id: str) -> None:
        self._l1.invalidate(session_id)
        with self._pool.connection() as conn:
            conn.execute("DELETE FROM app_session WHERE session_id = %s", (session_id,))
            conn.commit()
        self._l1.invalidate(session_id)

    def touch(
        self,
        session_id: str,
        *,
        access_token: str,
        refresh_token: str,
    ) -> StoredSession | None:
        self._l1.invalidate(session_id)
        expires = _now() + SESSION_TTL
        with self._pool.connection() as conn:
            conn.execute(
                """
                UPDATE app_session
                SET access_token = %s, refresh_token = %s, expires_at = %s
                WHERE session_id = %s
                """,
                (access_token, refresh_token, expires, session_id),
            )
            conn.commit()
        self._l1.invalidate(session_id)
        return self.get(session_id)


def require_session(store: SessionStore, session_id: str | None) -> StoredSession:
    if not session_id:
        raise SessionExpiredError("Not signed in")
    session = store.get(session_id)
    if session is None:
        raise SessionExpiredError("Session expired")
    return session

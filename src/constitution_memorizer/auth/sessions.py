"""Server-side session store (in-memory and PostgreSQL)."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol
from uuid import UUID

from constitution_memorizer.auth.exceptions import SessionExpiredError
from constitution_memorizer.auth.models import AuthenticatedUser

SESSION_COOKIE_NAME = "rtc_session"
CSRF_COOKIE_NAME = "rtc_csrf"
SESSION_TTL = timedelta(days=14)


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
    """Persist sessions in PostgreSQL app_session table."""

    def __init__(self, pool) -> None:
        self._pool = pool

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
        return session

    def get(self, session_id: str) -> StoredSession | None:
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
        expires_at = row[10]
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
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
        created = row[11]
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        return StoredSession(
            session_id=row[0],
            user=user,
            access_token=row[2],
            refresh_token=row[3],
            csrf_token=row[4],
            expires_at=expires_at,
            created_at=created,
        )

    def delete(self, session_id: str) -> None:
        with self._pool.connection() as conn:
            conn.execute("DELETE FROM app_session WHERE session_id = %s", (session_id,))
            conn.commit()

    def touch(
        self,
        session_id: str,
        *,
        access_token: str,
        refresh_token: str,
    ) -> StoredSession | None:
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
        return self.get(session_id)


def require_session(store: SessionStore, session_id: str | None) -> StoredSession:
    if not session_id:
        raise SessionExpiredError("Not signed in")
    session = store.get(session_id)
    if session is None:
        raise SessionExpiredError("Session expired")
    return session

"""Hot-path access store: admin role + effective manual grant per user.

Three read paths with different guarantees, never conflated:

- ``is_admin`` — authoritative role lookup used by ``/admin`` authorization
  on every request. Revoking the role takes effect on the next request.
- ``resolve_access_override`` — single round trip fetching the role bit and
  the effective grant together, memoized per request by the entitlement
  layer. Independent of ``ADMIN_ENABLED``: the paywall bypass follows the
  ``user_roles`` row, not the console flag.
- ``is_admin_hint`` — a ~60s process-local cache over ``is_admin`` used only
  for the cosmetic account-menu link. Authorization never reads it.

Overlap rule for grants: the grant giving the furthest access wins, and an
indefinite grant (``ends_at IS NULL``) beats any dated one.
"""

from __future__ import annotations

import sqlite3
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol
from uuid import UUID

from constitution_memorizer.progress.user_ids import as_user_id


@dataclass(frozen=True)
class EffectiveGrant:
    """The winning active manual grant for a user (None ends_at = indefinite)."""

    grant_id: str
    source: str
    starts_at: datetime
    ends_at: datetime | None


@dataclass(frozen=True)
class AccessOverride:
    """Role + effective grant, resolved in one lookup for feature resolution."""

    is_admin: bool = False
    effective_grant: EffectiveGrant | None = None

    @property
    def has_recall_access(self) -> bool:
        return self.is_admin or self.effective_grant is not None


class AccessStore(Protocol):
    def is_admin(self, user_id: UUID | str) -> bool: ...

    def resolve_access_override(
        self, user_id: UUID | str, now: datetime
    ) -> AccessOverride: ...


# One statement: role bit + winning grant in a single round trip.
_PG_OVERRIDE_SQL = """
SELECT
    EXISTS(
        SELECT 1 FROM user_roles WHERE user_id = %(uid)s AND role = 'admin'
    ) AS is_admin,
    g.id AS grant_id, g.source, g.starts_at, g.ends_at
FROM (SELECT 1) AS one
LEFT JOIN (
    SELECT id, source, starts_at, ends_at
    FROM access_grants
    WHERE user_id = %(uid)s
      AND revoked_at IS NULL
      AND starts_at <= %(now)s
      AND (ends_at IS NULL OR ends_at > %(now)s)
    ORDER BY (ends_at IS NULL) DESC, ends_at DESC
    LIMIT 1
) AS g ON TRUE
"""

_SQLITE_OVERRIDE_SQL = """
SELECT
    EXISTS(
        SELECT 1 FROM user_roles WHERE user_id = :uid AND role = 'admin'
    ) AS is_admin,
    g.id AS grant_id, g.source, g.starts_at, g.ends_at
FROM (SELECT 1) AS one
LEFT JOIN (
    SELECT id, source, starts_at, ends_at
    FROM access_grants
    WHERE user_id = :uid
      AND revoked_at IS NULL
      AND starts_at <= :now
      AND (ends_at IS NULL OR ends_at > :now)
    ORDER BY (ends_at IS NULL) DESC, ends_at DESC
    LIMIT 1
) AS g ON 1
"""


def _parse_ts(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    parsed = datetime.fromisoformat(str(value))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _row_override(row: Any) -> AccessOverride:
    grant = None
    if row["grant_id"] is not None:
        starts = _parse_ts(row["starts_at"])
        assert starts is not None
        grant = EffectiveGrant(
            grant_id=str(row["grant_id"]),
            source=str(row["source"]),
            starts_at=starts,
            ends_at=_parse_ts(row["ends_at"]),
        )
    return AccessOverride(is_admin=bool(row["is_admin"]), effective_grant=grant)


class PostgresAccessStore:
    def __init__(self, pool: Any) -> None:
        from psycopg.rows import dict_row

        self._pool = pool
        self._dict_row = dict_row

    def is_admin(self, user_id: UUID | str) -> bool:
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM user_roles WHERE user_id = %s AND role = 'admin'",
                    (as_user_id(user_id),),
                )
                return cur.fetchone() is not None

    def resolve_access_override(
        self, user_id: UUID | str, now: datetime
    ) -> AccessOverride:
        with self._pool.connection() as conn:
            with conn.cursor(row_factory=self._dict_row) as cur:
                cur.execute(
                    _PG_OVERRIDE_SQL, {"uid": as_user_id(user_id), "now": now}
                )
                row = cur.fetchone()
        return _row_override(row) if row is not None else AccessOverride()


class SqliteAccessStore:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def is_admin(self, user_id: UUID | str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM user_roles WHERE user_id = ? AND role = 'admin'",
            (as_user_id(user_id),),
        ).fetchone()
        return row is not None

    def resolve_access_override(
        self, user_id: UUID | str, now: datetime
    ) -> AccessOverride:
        row = self._conn.execute(
            _SQLITE_OVERRIDE_SQL,
            {
                "uid": as_user_id(user_id),
                "now": now.replace(microsecond=0).isoformat(),
            },
        ).fetchone()
        return _row_override(row) if row is not None else AccessOverride()


class AdminHintCache:
    """Process-local TTL/LRU cache for the cosmetic nav link only.

    A revoked admin may see the link for up to ``ttl`` more seconds; the
    console itself re-checks the authoritative store and 404s immediately.
    """

    def __init__(self, ttl_seconds: float = 60.0, max_entries: int = 512) -> None:
        self._ttl = ttl_seconds
        self._max = max_entries
        self._lock = threading.Lock()
        self._entries: OrderedDict[str, tuple[bool, float]] = OrderedDict()

    def get(self, user_id: UUID | str, load: Any) -> bool:
        key = as_user_id(user_id)
        now = time.monotonic()
        with self._lock:
            hit = self._entries.get(key)
            if hit is not None and hit[1] > now:
                self._entries.move_to_end(key)
                return hit[0]
        value = bool(load())
        with self._lock:
            self._entries[key] = (value, now + self._ttl)
            self._entries.move_to_end(key)
            while len(self._entries) > self._max:
                self._entries.popitem(last=False)
        return value

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

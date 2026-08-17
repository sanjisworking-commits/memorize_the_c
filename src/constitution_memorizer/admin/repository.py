"""Cold-path admin-console repository (users, grants, audit, roster).

Postgres and SQLite implementations of the same surface. Grant mutations
write their audit row in the same transaction as the mutation — if the audit
insert fails, the mutation rolls back (both backends).

Timestamps are returned as ISO-8601 strings for display; grant state
(active / scheduled / ended / revoked) is derived at render time from the
timestamps — there is no background expiry job.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterator
from uuid import UUID

from contextlib import contextmanager

from constitution_memorizer.admin.audit import (
    AuditEntry,
    PG_AUDIT_INSERT,
    SQLITE_AUDIT_INSERT,
    pg_audit_params,
    sqlite_audit_params,
)
from constitution_memorizer.progress.user_ids import as_user_id


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _loads(value: Any) -> dict | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(str(value))
    except (TypeError, ValueError):
        return None
    return parsed if isinstance(parsed, dict) else None


@dataclass(frozen=True)
class UserRow:
    """One /admin/users search result with render-ready access facts."""

    user_id: str
    display_name: str | None
    email: str | None
    phone: str | None
    last_sign_in_at: str | None
    created_at: str | None
    is_admin: bool
    claimed_count: int
    grant_source: str | None
    grant_ends_at: str | None


@dataclass(frozen=True)
class UserOverview:
    user_id: str
    display_name: str | None
    email: str | None
    phone: str | None
    created_at: str | None
    last_sign_in_at: str | None
    is_admin: bool
    admin_since: str | None
    admin_created_by: str | None


@dataclass(frozen=True)
class GrantRow:
    id: str
    user_id: str
    user_display: str | None
    source: str
    starts_at: str
    ends_at: str | None
    reason: str | None
    granted_by: str | None
    granted_by_display: str | None
    created_at: str
    revoked_at: str | None

    def state(self, now: datetime) -> str:
        """active / scheduled / ended / revoked, derived from timestamps."""
        if self.revoked_at is not None:
            return "revoked"
        now_iso = now.replace(microsecond=0).isoformat()
        if self.starts_at > now_iso:
            return "scheduled"
        if self.ends_at is not None and self.ends_at <= now_iso:
            return "ended"
        return "active"


@dataclass(frozen=True)
class AdminRow:
    user_id: str
    display_name: str | None
    email: str | None
    created_at: str | None
    created_by: str | None
    created_by_display: str | None


@dataclass(frozen=True)
class AuditRow:
    id: str
    admin_user_id: str
    admin_display: str | None
    action: str
    target_user_id: str | None
    target_display: str | None
    target_type: str | None
    target_id: str | None
    before_state: dict | None
    after_state: dict | None
    reason: str | None
    created_at: str


@dataclass(frozen=True)
class HomeCounts:
    total_users: int
    free_users: int
    active_grants: int
    admins: int


def _row_user(row: Any) -> UserRow:
    return UserRow(
        user_id=str(row["user_id"]),
        display_name=row["display_name"],
        email=row["email"],
        phone=row["phone"],
        last_sign_in_at=_iso(row["last_sign_in_at"]),
        created_at=_iso(row["created_at"]),
        is_admin=bool(row["is_admin"]),
        claimed_count=int(row["claimed_count"] or 0),
        grant_source=row["grant_source"],
        grant_ends_at=_iso(row["grant_ends_at"]),
    )


def _row_overview(row: Any) -> UserOverview:
    return UserOverview(
        user_id=str(row["user_id"]),
        display_name=row["display_name"],
        email=row["email"],
        phone=row["phone"],
        created_at=_iso(row["created_at"]),
        last_sign_in_at=_iso(row["last_sign_in_at"]),
        is_admin=row["admin_since"] is not None,
        admin_since=_iso(row["admin_since"]),
        admin_created_by=(
            str(row["admin_created_by"]) if row["admin_created_by"] else None
        ),
    )


def _row_grant(row: Any) -> GrantRow:
    starts = _iso(row["starts_at"])
    created = _iso(row["created_at"])
    assert starts is not None and created is not None
    return GrantRow(
        id=str(row["id"]),
        user_id=str(row["user_id"]),
        user_display=row["user_display"],
        source=str(row["source"]),
        starts_at=starts,
        ends_at=_iso(row["ends_at"]),
        reason=row["reason"],
        granted_by=str(row["granted_by"]) if row["granted_by"] else None,
        granted_by_display=row["granted_by_display"],
        created_at=created,
        revoked_at=_iso(row["revoked_at"]),
    )


def _row_admin(row: Any) -> AdminRow:
    return AdminRow(
        user_id=str(row["user_id"]),
        display_name=row["display_name"],
        email=row["email"],
        created_at=_iso(row["created_at"]),
        created_by=str(row["created_by"]) if row["created_by"] else None,
        created_by_display=row["created_by_display"],
    )


def _row_audit(row: Any) -> AuditRow:
    created = _iso(row["created_at"])
    assert created is not None
    return AuditRow(
        id=str(row["id"]),
        admin_user_id=str(row["admin_user_id"]),
        admin_display=row["admin_display"],
        action=str(row["action"]),
        target_user_id=(
            str(row["target_user_id"]) if row["target_user_id"] else None
        ),
        target_display=row["target_display"],
        target_type=row["target_type"],
        target_id=row["target_id"],
        before_state=_loads(row["before_state"]),
        after_state=_loads(row["after_state"]),
        reason=row["reason"],
        created_at=created,
    )


def _grant_audit_states(
    *, grant_id: str, source: str, ends_at: str | None, reason: str | None
) -> dict:
    return {
        "grant_id": grant_id,
        "source": source,
        "ends_at": ends_at,
        "reason": reason,
    }


_USER_SELECT = """
SELECT p.user_id, p.display_name, p.email, p.phone,
       p.last_sign_in_at, p.created_at,
       EXISTS(
           SELECT 1 FROM user_roles r
           WHERE r.user_id = p.user_id AND r.role = 'admin'
       ) AS is_admin,
       (
           SELECT COUNT(*) FROM user_free_articles f
           WHERE f.user_id = {uid_cast}
       ) AS claimed_count,
       (
           SELECT a.source FROM access_grants a
           WHERE a.user_id = p.user_id AND a.revoked_at IS NULL
             AND a.starts_at <= {now} AND (a.ends_at IS NULL OR a.ends_at > {now})
           ORDER BY (a.ends_at IS NULL) DESC, a.ends_at DESC LIMIT 1
       ) AS grant_source,
       (
           SELECT a.ends_at FROM access_grants a
           WHERE a.user_id = p.user_id AND a.revoked_at IS NULL
             AND a.starts_at <= {now} AND (a.ends_at IS NULL OR a.ends_at > {now})
           ORDER BY (a.ends_at IS NULL) DESC, a.ends_at DESC LIMIT 1
       ) AS grant_ends_at
FROM user_profile p
"""

_USER_ORDER = """
ORDER BY (p.last_sign_in_at IS NULL), p.last_sign_in_at DESC, p.created_at DESC
LIMIT {limit}
"""

_OVERVIEW_SELECT = """
SELECT p.user_id, p.display_name, p.email, p.phone, p.created_at,
       p.last_sign_in_at,
       r.created_at AS admin_since, r.created_by AS admin_created_by
FROM user_profile p
LEFT JOIN user_roles r ON r.user_id = p.user_id AND r.role = 'admin'
WHERE p.user_id = {ph}
"""

_GRANTS_SELECT = """
SELECT a.id, a.user_id, a.source, a.starts_at, a.ends_at, a.reason,
       a.granted_by, a.created_at, a.revoked_at,
       p.display_name AS user_display,
       pb.display_name AS granted_by_display
FROM access_grants a
LEFT JOIN user_profile p ON p.user_id = a.user_id
LEFT JOIN user_profile pb ON pb.user_id = a.granted_by
"""

_ADMINS_SELECT = """
SELECT r.user_id, r.created_at, r.created_by,
       p.display_name, p.email,
       pb.display_name AS created_by_display
FROM user_roles r
LEFT JOIN user_profile p ON p.user_id = r.user_id
LEFT JOIN user_profile pb ON pb.user_id = r.created_by
WHERE r.role = 'admin'
ORDER BY r.created_at ASC
"""

_AUDIT_SELECT = """
SELECT e.id, e.admin_user_id, e.action, e.target_user_id, e.target_type,
       e.target_id, e.before_state, e.after_state, e.reason, e.created_at,
       pa.display_name AS admin_display,
       pt.display_name AS target_display
FROM admin_audit_log e
LEFT JOIN user_profile pa ON pa.user_id = e.admin_user_id
LEFT JOIN user_profile pt ON pt.user_id = e.target_user_id
"""


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
    except (ValueError, AttributeError, TypeError):
        return False
    return True


class PostgresAdminRepository:
    def __init__(self, pool: Any) -> None:
        from psycopg.rows import dict_row

        self._pool = pool
        self._dict_row = dict_row

    @contextmanager
    def _cursor(self) -> Iterator[tuple[Any, Any]]:
        with self._pool.connection() as conn:
            with conn.cursor(row_factory=self._dict_row) as cur:
                yield conn, cur

    # ------------------------------------------------------------------ #
    # Users                                                              #
    # ------------------------------------------------------------------ #
    def search_users(self, q: str, *, limit: int = 50) -> list[UserRow]:
        q = (q or "").strip()
        now = _utc_now()
        base = _USER_SELECT.format(uid_cast="p.user_id::text", now="%(now)s")
        order = _USER_ORDER.format(limit="%(limit)s")
        params: dict[str, Any] = {"now": now, "limit": limit}
        if not q:
            sql = base + order
        elif _is_uuid(q):
            sql = base + "WHERE p.user_id = %(uid)s" + order
            params["uid"] = q
        else:
            sql = (
                base
                + """WHERE p.display_name ILIKE %(pat)s
                     OR p.email ILIKE %(pat)s
                     OR p.phone ILIKE %(pat)s"""
                + order
            )
            params["pat"] = f"%{q}%"
        with self._cursor() as (_conn, cur):
            cur.execute(sql, params)
            rows = cur.fetchall()
        return [_row_user(r) for r in rows]

    def get_user_overview(self, user_id: UUID | str) -> UserOverview | None:
        with self._cursor() as (_conn, cur):
            cur.execute(_OVERVIEW_SELECT.format(ph="%s"), (as_user_id(user_id),))
            row = cur.fetchone()
        return _row_overview(row) if row else None

    def counts(self) -> HomeCounts:
        now = _utc_now()
        with self._cursor() as (_conn, cur):
            cur.execute(
                """
                SELECT
                    (SELECT COUNT(*) FROM user_profile) AS total_users,
                    (SELECT COUNT(*) FROM user_roles WHERE role = 'admin') AS admins,
                    (SELECT COUNT(*) FROM access_grants
                     WHERE revoked_at IS NULL AND starts_at <= %(now)s
                       AND (ends_at IS NULL OR ends_at > %(now)s)) AS active_grants,
                    (SELECT COUNT(*) FROM user_profile p
                     WHERE NOT EXISTS(
                             SELECT 1 FROM user_roles r
                             WHERE r.user_id = p.user_id AND r.role = 'admin')
                       AND NOT EXISTS(
                             SELECT 1 FROM access_grants a
                             WHERE a.user_id = p.user_id AND a.revoked_at IS NULL
                               AND a.starts_at <= %(now)s
                               AND (a.ends_at IS NULL OR a.ends_at > %(now)s))
                    ) AS free_users
                """,
                {"now": now},
            )
            row = cur.fetchone()
        return HomeCounts(
            total_users=int(row["total_users"]),
            free_users=int(row["free_users"]),
            active_grants=int(row["active_grants"]),
            admins=int(row["admins"]),
        )

    # ------------------------------------------------------------------ #
    # Grants (mutation + audit are one transaction)                      #
    # ------------------------------------------------------------------ #
    def list_grants(
        self,
        user_id: UUID | str | None = None,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[GrantRow]:
        sql = _GRANTS_SELECT
        params: list[Any] = []
        if user_id is not None:
            sql += "WHERE a.user_id = %s\n"
            params.append(as_user_id(user_id))
        sql += "ORDER BY a.created_at DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])
        with self._cursor() as (_conn, cur):
            cur.execute(sql, params)
            rows = cur.fetchall()
        return [_row_grant(r) for r in rows]

    def get_grant(self, grant_id: str) -> GrantRow | None:
        with self._cursor() as (_conn, cur):
            cur.execute(_GRANTS_SELECT + "WHERE a.id = %s", (grant_id,))
            row = cur.fetchone()
        return _row_grant(row) if row else None

    def create_grant(
        self,
        *,
        user_id: UUID | str,
        source: str,
        ends_at: datetime | None,
        reason: str,
        granted_by: UUID | str,
    ) -> GrantRow:
        now = _utc_now()
        with self._cursor() as (conn, cur):
            cur.execute(
                """
                INSERT INTO access_grants (
                    user_id, source, starts_at, ends_at, reason,
                    granted_by, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    as_user_id(user_id),
                    source,
                    now,
                    ends_at,
                    reason,
                    as_user_id(granted_by),
                    now,
                ),
            )
            grant_id = str(cur.fetchone()["id"])
            entry = AuditEntry(
                admin_user_id=as_user_id(granted_by),
                action="grant_access",
                target_user_id=as_user_id(user_id),
                target_type="access_grant",
                target_id=grant_id,
                before_state=None,
                after_state=_grant_audit_states(
                    grant_id=grant_id,
                    source=source,
                    ends_at=_iso(ends_at),
                    reason=reason,
                ),
                reason=reason,
            )
            cur.execute(PG_AUDIT_INSERT, pg_audit_params(entry, now))
            conn.commit()
        grant = self.get_grant(grant_id)
        assert grant is not None
        return grant

    def revoke_grant(
        self, grant_id: str, *, admin_user_id: UUID | str
    ) -> GrantRow | None:
        now = _utc_now()
        with self._cursor() as (conn, cur):
            cur.execute(
                """
                UPDATE access_grants SET revoked_at = %s
                WHERE id = %s AND revoked_at IS NULL
                RETURNING user_id, source, ends_at, reason
                """,
                (now, grant_id),
            )
            row = cur.fetchone()
            if row is None:
                conn.rollback()
                return None
            states = _grant_audit_states(
                grant_id=grant_id,
                source=str(row["source"]),
                ends_at=_iso(row["ends_at"]),
                reason=row["reason"],
            )
            entry = AuditEntry(
                admin_user_id=as_user_id(admin_user_id),
                action="revoke_grant",
                target_user_id=str(row["user_id"]),
                target_type="access_grant",
                target_id=grant_id,
                before_state={**states, "revoked_at": None},
                after_state={**states, "revoked_at": _iso(now)},
            )
            cur.execute(PG_AUDIT_INSERT, pg_audit_params(entry, now))
            conn.commit()
        return self.get_grant(grant_id)

    # ------------------------------------------------------------------ #
    # Audit                                                              #
    # ------------------------------------------------------------------ #
    def write_audit(self, entry: AuditEntry) -> None:
        with self._cursor() as (conn, cur):
            cur.execute(PG_AUDIT_INSERT, pg_audit_params(entry, _utc_now()))
            conn.commit()

    def list_audit(
        self,
        target_user_id: UUID | str | None = None,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditRow]:
        sql = _AUDIT_SELECT
        params: list[Any] = []
        if target_user_id is not None:
            sql += "WHERE e.target_user_id = %s\n"
            params.append(as_user_id(target_user_id))
        sql += "ORDER BY e.created_at DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])
        with self._cursor() as (_conn, cur):
            cur.execute(sql, params)
            rows = cur.fetchall()
        return [_row_audit(r) for r in rows]

    def list_admins(self) -> list[AdminRow]:
        with self._cursor() as (_conn, cur):
            cur.execute(_ADMINS_SELECT)
            rows = cur.fetchall()
        return [_row_admin(r) for r in rows]


class SqliteAdminRepository:
    """SQLite twin for local dev and tests; timestamps are ISO-8601 UTC text."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def search_users(self, q: str, *, limit: int = 50) -> list[UserRow]:
        q = (q or "").strip()
        now_iso = _utc_now().isoformat()
        base = _USER_SELECT.format(uid_cast="p.user_id", now=":now")
        order = _USER_ORDER.format(limit=":limit")
        params: dict[str, Any] = {"now": now_iso, "limit": limit}
        if not q:
            sql = base + order
        elif _is_uuid(q):
            sql = base + "WHERE p.user_id = :uid" + order
            params["uid"] = q
        else:
            sql = (
                base
                + """WHERE LOWER(p.display_name) LIKE :pat
                     OR LOWER(p.email) LIKE :pat
                     OR LOWER(p.phone) LIKE :pat"""
                + order
            )
            params["pat"] = f"%{q.lower()}%"
        rows = self._conn.execute(sql, params).fetchall()
        return [_row_user(r) for r in rows]

    def get_user_overview(self, user_id: UUID | str) -> UserOverview | None:
        row = self._conn.execute(
            _OVERVIEW_SELECT.format(ph="?"), (as_user_id(user_id),)
        ).fetchone()
        return _row_overview(row) if row else None

    def counts(self) -> HomeCounts:
        now_iso = _utc_now().isoformat()
        row = self._conn.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM user_profile) AS total_users,
                (SELECT COUNT(*) FROM user_roles WHERE role = 'admin') AS admins,
                (SELECT COUNT(*) FROM access_grants
                 WHERE revoked_at IS NULL AND starts_at <= :now
                   AND (ends_at IS NULL OR ends_at > :now)) AS active_grants,
                (SELECT COUNT(*) FROM user_profile p
                 WHERE NOT EXISTS(
                         SELECT 1 FROM user_roles r
                         WHERE r.user_id = p.user_id AND r.role = 'admin')
                   AND NOT EXISTS(
                         SELECT 1 FROM access_grants a
                         WHERE a.user_id = p.user_id AND a.revoked_at IS NULL
                           AND a.starts_at <= :now
                           AND (a.ends_at IS NULL OR a.ends_at > :now))
                ) AS free_users
            """,
            {"now": now_iso},
        ).fetchone()
        return HomeCounts(
            total_users=int(row["total_users"]),
            free_users=int(row["free_users"]),
            active_grants=int(row["active_grants"]),
            admins=int(row["admins"]),
        )

    def list_grants(
        self,
        user_id: UUID | str | None = None,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[GrantRow]:
        sql = _GRANTS_SELECT
        params: list[Any] = []
        if user_id is not None:
            sql += "WHERE a.user_id = ?\n"
            params.append(as_user_id(user_id))
        sql += "ORDER BY a.created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        rows = self._conn.execute(sql, params).fetchall()
        return [_row_grant(r) for r in rows]

    def get_grant(self, grant_id: str) -> GrantRow | None:
        row = self._conn.execute(
            _GRANTS_SELECT + "WHERE a.id = ?", (grant_id,)
        ).fetchone()
        return _row_grant(row) if row else None

    def create_grant(
        self,
        *,
        user_id: UUID | str,
        source: str,
        ends_at: datetime | None,
        reason: str,
        granted_by: UUID | str,
    ) -> GrantRow:
        now = _utc_now()
        now_iso = now.isoformat()
        grant_id = str(uuid.uuid4())
        entry = AuditEntry(
            admin_user_id=as_user_id(granted_by),
            action="grant_access",
            target_user_id=as_user_id(user_id),
            target_type="access_grant",
            target_id=grant_id,
            before_state=None,
            after_state=_grant_audit_states(
                grant_id=grant_id,
                source=source,
                ends_at=_iso(ends_at),
                reason=reason,
            ),
            reason=reason,
        )
        try:
            self._conn.execute(
                """
                INSERT INTO access_grants (
                    id, user_id, source, starts_at, ends_at, reason,
                    granted_by, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    grant_id,
                    as_user_id(user_id),
                    source,
                    now_iso,
                    ends_at.isoformat() if ends_at else None,
                    reason,
                    as_user_id(granted_by),
                    now_iso,
                ),
            )
            self._conn.execute(
                SQLITE_AUDIT_INSERT,
                sqlite_audit_params(entry, str(uuid.uuid4()), now_iso),
            )
        except Exception:
            self._conn.rollback()
            raise
        self._conn.commit()
        grant = self.get_grant(grant_id)
        assert grant is not None
        return grant

    def revoke_grant(
        self, grant_id: str, *, admin_user_id: UUID | str
    ) -> GrantRow | None:
        now_iso = _utc_now().isoformat()
        row = self._conn.execute(
            """
            SELECT user_id, source, ends_at, reason FROM access_grants
            WHERE id = ? AND revoked_at IS NULL
            """,
            (grant_id,),
        ).fetchone()
        if row is None:
            return None
        states = _grant_audit_states(
            grant_id=grant_id,
            source=str(row["source"]),
            ends_at=row["ends_at"],
            reason=row["reason"],
        )
        entry = AuditEntry(
            admin_user_id=as_user_id(admin_user_id),
            action="revoke_grant",
            target_user_id=str(row["user_id"]),
            target_type="access_grant",
            target_id=grant_id,
            before_state={**states, "revoked_at": None},
            after_state={**states, "revoked_at": now_iso},
        )
        try:
            self._conn.execute(
                "UPDATE access_grants SET revoked_at = ? WHERE id = ?",
                (now_iso, grant_id),
            )
            self._conn.execute(
                SQLITE_AUDIT_INSERT,
                sqlite_audit_params(entry, str(uuid.uuid4()), now_iso),
            )
        except Exception:
            self._conn.rollback()
            raise
        self._conn.commit()
        return self.get_grant(grant_id)

    def write_audit(self, entry: AuditEntry) -> None:
        self._conn.execute(
            SQLITE_AUDIT_INSERT,
            sqlite_audit_params(entry, str(uuid.uuid4()), _utc_now().isoformat()),
        )
        self._conn.commit()

    def list_audit(
        self,
        target_user_id: UUID | str | None = None,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditRow]:
        sql = _AUDIT_SELECT
        params: list[Any] = []
        if target_user_id is not None:
            sql += "WHERE e.target_user_id = ?\n"
            params.append(as_user_id(target_user_id))
        sql += "ORDER BY e.created_at DESC, e.id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        rows = self._conn.execute(sql, params).fetchall()
        return [_row_audit(r) for r in rows]

    def list_admins(self) -> list[AdminRow]:
        rows = self._conn.execute(_ADMINS_SELECT).fetchall()
        return [_row_admin(r) for r in rows]

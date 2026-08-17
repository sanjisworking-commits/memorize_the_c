"""psycopg repository for contact_messages (server-side DATABASE_URL only)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from psycopg.rows import dict_row

from constitution_memorizer.admin.audit import (
    AuditEntry,
    PG_AUDIT_INSERT,
    pg_audit_params,
)

# Stored status values (DB CHECK constraint). Contact has no dismissed value;
# the admin UI simply omits that button.
CONTACT_MESSAGE_STATUSES = ("new", "reviewing", "resolved")


@dataclass(frozen=True)
class ContactMessage:
    """Created contact message row (defaults filled by PostgreSQL)."""

    id: UUID
    status: str
    created_at: datetime
    topic: str
    message: str
    page_url: str | None
    reporter_email: str | None


class PostgresContactMessageRepository:
    """Insert contact messages via parameterized SQL (no ORM)."""

    def __init__(self, pool: Any) -> None:
        self._pool = pool

    def create_message(
        self,
        *,
        topic: str,
        message: str,
        page_url: str | None,
        reporter_email: str | None,
    ) -> ContactMessage:
        with self._pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    INSERT INTO contact_messages (
                        topic,
                        message,
                        page_url,
                        reporter_email
                    ) VALUES (%s, %s, %s, %s)
                    RETURNING id, status, created_at, topic, message, page_url, reporter_email
                    """,
                    (
                        topic,
                        message,
                        page_url,
                        reporter_email,
                    ),
                )
                row = cur.fetchone()
            conn.commit()
        if row is None:
            raise RuntimeError("contact_messages INSERT returned no row")
        return _row_to_message(row)


    # ------------------------------------------------------------------ #
    # Admin inbox (read + status transitions)                            #
    # ------------------------------------------------------------------ #
    def list_messages(
        self,
        *,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ContactMessage]:
        sql = (
            "SELECT id, status, created_at, topic, message, page_url, "
            "reporter_email FROM contact_messages"
        )
        params: list[Any] = []
        if status is not None:
            sql += " WHERE status = %s"
            params.append(status)
        sql += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])
        with self._pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
        return [_row_to_message(r) for r in rows]

    def get_message(self, message_id: str) -> ContactMessage | None:
        with self._pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT id, status, created_at, topic, message, page_url,
                           reporter_email
                    FROM contact_messages WHERE id = %s
                    """,
                    (message_id,),
                )
                row = cur.fetchone()
        return _row_to_message(row) if row else None

    def count_by_status(self, status: str) -> int:
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) FROM contact_messages WHERE status = %s",
                    (status,),
                )
                return int(cur.fetchone()[0])

    def update_status(
        self,
        message_id: str,
        status: str,
        *,
        audit: AuditEntry | None = None,
    ) -> tuple[str, str] | None:
        """Transition a message; the audit row commits in the same transaction.

        Returns (before, after) or None when the message does not exist.
        """
        with self._pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    UPDATE contact_messages AS m SET status = %s
                    FROM (SELECT id, status FROM contact_messages WHERE id = %s
                          FOR UPDATE) AS old
                    WHERE m.id = old.id
                    RETURNING old.status AS before_status
                    """,
                    (status, message_id),
                )
                row = cur.fetchone()
                if row is None:
                    conn.rollback()
                    return None
                if audit is not None:
                    cur.execute(
                        PG_AUDIT_INSERT,
                        pg_audit_params(audit, datetime.now(timezone.utc)),
                    )
            conn.commit()
        return (str(row["before_status"]), status)


def _row_to_message(row: Any) -> ContactMessage:
    message_id = row["id"]
    if not isinstance(message_id, UUID):
        message_id = UUID(str(message_id))
    return ContactMessage(
        id=message_id,
        status=str(row["status"]),
        created_at=row["created_at"],
        topic=str(row["topic"]),
        message=str(row["message"]),
        page_url=row["page_url"],
        reporter_email=row["reporter_email"],
    )

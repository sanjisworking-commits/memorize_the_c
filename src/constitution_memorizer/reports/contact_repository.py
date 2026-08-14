"""psycopg repository for contact_messages (server-side DATABASE_URL only)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from psycopg.rows import dict_row


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

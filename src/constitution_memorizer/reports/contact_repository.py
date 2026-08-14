"""psycopg repository for contact_messages (server-side DATABASE_URL only)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID


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

    def __init__(self, dsn: str) -> None:
        import psycopg
        from psycopg.rows import dict_row

        self._dsn = dsn
        self._psycopg = psycopg
        self._dict_row = dict_row

    def _connect(self):
        return self._psycopg.connect(self._dsn, row_factory=self._dict_row)

    def create_message(
        self,
        *,
        topic: str,
        message: str,
        page_url: str | None,
        reporter_email: str | None,
    ) -> ContactMessage:
        with self._connect() as conn:
            row = conn.execute(
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
            ).fetchone()
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

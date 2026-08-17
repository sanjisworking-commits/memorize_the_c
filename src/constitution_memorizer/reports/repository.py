"""psycopg repository for issue_reports (server-side DATABASE_URL only)."""

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

# Stored status values (DB CHECK constraint). The admin UI labels them
# New / Reviewing / Resolved / Dismissed without migrating the constraint.
ISSUE_REPORT_STATUSES = ("new", "reviewing", "fixed", "rejected")


@dataclass(frozen=True)
class IssueReport:
    """Created issue report row (defaults filled by PostgreSQL)."""

    id: UUID
    status: str
    created_at: datetime


@dataclass(frozen=True)
class IssueReportRow:
    """Full row for the admin inbox."""

    id: str
    article_number: str | None
    section: str | None
    selected_text: str | None
    issue_type: str
    description: str
    suggested_correction: str | None
    source_url: str | None
    reporter_email: str | None
    page_url: str | None
    status: str
    created_at: str


class PostgresIssueReportRepository:
    """Insert issue reports via parameterized SQL (no ORM)."""

    def __init__(self, pool: Any) -> None:
        self._pool = pool

    def create_report(
        self,
        *,
        article_number: str | None,
        section: str | None,
        selected_text: str | None,
        issue_type: str,
        description: str,
        suggested_correction: str | None,
        source_url: str | None,
        reporter_email: str | None,
        page_url: str,
    ) -> IssueReport:
        with self._pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    INSERT INTO issue_reports (
                        article_number,
                        section,
                        selected_text,
                        issue_type,
                        description,
                        suggested_correction,
                        source_url,
                        reporter_email,
                        page_url
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id, status, created_at
                    """,
                    (
                        article_number,
                        section,
                        selected_text,
                        issue_type,
                        description,
                        suggested_correction,
                        source_url,
                        reporter_email,
                        page_url,
                    ),
                )
                row = cur.fetchone()
            conn.commit()
        if row is None:
            raise RuntimeError("issue_reports INSERT returned no row")
        return _row_to_report(row)


    # ------------------------------------------------------------------ #
    # Admin inbox (read + status transitions)                            #
    # ------------------------------------------------------------------ #
    def list_reports(
        self,
        *,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[IssueReportRow]:
        sql = "SELECT * FROM issue_reports"
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
        return [_row_to_report_row(r) for r in rows]

    def get_report(self, report_id: str) -> IssueReportRow | None:
        with self._pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    "SELECT * FROM issue_reports WHERE id = %s", (report_id,)
                )
                row = cur.fetchone()
        return _row_to_report_row(row) if row else None

    def count_by_status(self, status: str) -> int:
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) FROM issue_reports WHERE status = %s",
                    (status,),
                )
                return int(cur.fetchone()[0])

    def update_status(
        self,
        report_id: str,
        status: str,
        *,
        audit: AuditEntry | None = None,
    ) -> tuple[str, str] | None:
        """Transition a report; the audit row commits in the same transaction.

        Returns (before, after) or None when the report does not exist.
        """
        with self._pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    UPDATE issue_reports AS r SET status = %s
                    FROM (SELECT id, status FROM issue_reports WHERE id = %s
                          FOR UPDATE) AS old
                    WHERE r.id = old.id
                    RETURNING old.status AS before_status
                    """,
                    (status, report_id),
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


def _row_to_report_row(row: Any) -> IssueReportRow:
    created = row["created_at"]
    return IssueReportRow(
        id=str(row["id"]),
        article_number=row["article_number"],
        section=row["section"],
        selected_text=row["selected_text"],
        issue_type=str(row["issue_type"]),
        description=str(row["description"]),
        suggested_correction=row["suggested_correction"],
        source_url=row["source_url"],
        reporter_email=row["reporter_email"],
        page_url=row["page_url"],
        status=str(row["status"]),
        created_at=created.isoformat()
        if hasattr(created, "isoformat")
        else str(created),
    )


def _row_to_report(row: Any) -> IssueReport:
    report_id = row["id"]
    if not isinstance(report_id, UUID):
        report_id = UUID(str(report_id))
    created = row["created_at"]
    return IssueReport(
        id=report_id,
        status=str(row["status"]),
        created_at=created,
    )

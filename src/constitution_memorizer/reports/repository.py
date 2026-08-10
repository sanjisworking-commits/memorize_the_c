"""psycopg repository for issue_reports (server-side DATABASE_URL only)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class IssueReport:
    """Created issue report row (defaults filled by PostgreSQL)."""

    id: UUID
    status: str
    created_at: datetime


class PostgresIssueReportRepository:
    """Insert issue reports via parameterized SQL (no ORM)."""

    def __init__(self, dsn: str) -> None:
        import psycopg
        from psycopg.rows import dict_row

        self._dsn = dsn
        self._psycopg = psycopg
        self._dict_row = dict_row

    def _connect(self):
        return self._psycopg.connect(self._dsn, row_factory=self._dict_row)

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
        with self._connect() as conn:
            row = conn.execute(
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
            ).fetchone()
            conn.commit()
        if row is None:
            raise RuntimeError("issue_reports INSERT returned no row")
        return _row_to_report(row)


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

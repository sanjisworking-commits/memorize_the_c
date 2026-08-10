"""Issue reports table for Report-an-issue (V1).

Revision ID: 20260810_0002
Revises: 20260801_0001
Create Date: 2026-08-10
"""

from __future__ import annotations

from alembic import op

revision = "20260810_0002"
down_revision = "20260801_0001"
branch_labels = None
depends_on = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS issue_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    article_number TEXT NULL,
    section TEXT NULL,
    selected_text TEXT NULL,
    issue_type TEXT NOT NULL,
    description TEXT NOT NULL,
    suggested_correction TEXT NULL,
    source_url TEXT NULL,
    reporter_email TEXT NULL,
    page_url TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'new',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT issue_reports_issue_type_check CHECK (
        issue_type IN (
            'incorrect_fact',
            'outdated_information',
            'interpretation_issue',
            'typo',
            'source_issue',
            'other'
        )
    ),
    CONSTRAINT issue_reports_status_check CHECK (
        status IN (
            'new',
            'reviewing',
            'fixed',
            'rejected'
        )
    )
);

CREATE INDEX IF NOT EXISTS idx_issue_reports_status ON issue_reports(status);
CREATE INDEX IF NOT EXISTS idx_issue_reports_article_number ON issue_reports(article_number);
CREATE INDEX IF NOT EXISTS idx_issue_reports_created_at ON issue_reports(created_at);

ALTER TABLE issue_reports ENABLE ROW LEVEL SECURITY;
"""


def upgrade() -> None:
    op.execute(SCHEMA)


def downgrade() -> None:
    op.execute(
        """
        DROP INDEX IF EXISTS idx_issue_reports_created_at;
        DROP INDEX IF EXISTS idx_issue_reports_article_number;
        DROP INDEX IF EXISTS idx_issue_reports_status;
        DROP TABLE IF EXISTS issue_reports;
        """
    )

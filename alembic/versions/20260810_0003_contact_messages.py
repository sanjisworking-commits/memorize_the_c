"""Contact messages table for Contact Us (V1).

Revision ID: 20260810_0003
Revises: 20260810_0002
Create Date: 2026-08-10
"""

from __future__ import annotations

from alembic import op

revision = "20260810_0003"
down_revision = "20260810_0002"
branch_labels = None
depends_on = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS contact_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    topic TEXT NOT NULL,
    message TEXT NOT NULL,
    page_url TEXT NULL,
    reporter_email TEXT NULL,
    status TEXT NOT NULL DEFAULT 'new',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT contact_messages_topic_check CHECK (
        topic IN (
            'technical_issue',
            'general_feedback',
            'feature_suggestion',
            'other'
        )
    ),
    CONSTRAINT contact_messages_status_check CHECK (
        status IN (
            'new',
            'reviewing',
            'resolved'
        )
    )
);

CREATE INDEX IF NOT EXISTS idx_contact_messages_status ON contact_messages(status);
CREATE INDEX IF NOT EXISTS idx_contact_messages_created_at ON contact_messages(created_at);

ALTER TABLE contact_messages ENABLE ROW LEVEL SECURITY;
"""


def upgrade() -> None:
    op.execute(SCHEMA)


def downgrade() -> None:
    op.execute(
        """
        DROP INDEX IF EXISTS idx_contact_messages_created_at;
        DROP INDEX IF EXISTS idx_contact_messages_status;
        DROP TABLE IF EXISTS contact_messages;
        """
    )

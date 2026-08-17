"""Google Calendar integration: connections (tombstone-able) + event mappings.

Revision ID: 20260819_0009
Revises: 20260818_0008
Create Date: 2026-08-19
"""

from __future__ import annotations

from alembic import op

revision = "20260819_0009"
down_revision = "20260818_0008"
branch_labels = None
depends_on = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS google_calendar_connections (
    user_id UUID PRIMARY KEY,
    google_calendar_id TEXT NULL,
    refresh_token_sealed TEXT NULL,
    sync_status TEXT NOT NULL DEFAULT 'pending'
        CONSTRAINT gcal_conn_status_check
        CHECK (sync_status IN ('ok', 'error', 'pending', 'disconnected')),
    sync_pending BOOLEAN NOT NULL DEFAULT FALSE,
    sync_requested_at TIMESTAMPTZ NULL,
    last_synced_at TIMESTAMPTZ NULL,
    last_error TEXT NULL,
    connected_at TIMESTAMPTZ NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS google_calendar_events (
    user_id UUID NOT NULL,
    local_date DATE NOT NULL,
    google_event_id TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    last_synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, local_date)
);

CREATE INDEX IF NOT EXISTS idx_gcal_events_user ON google_calendar_events(user_id);
"""

DOWNGRADE = """
DROP TABLE IF EXISTS google_calendar_events;
DROP TABLE IF EXISTS google_calendar_connections;
"""


def upgrade() -> None:
    op.execute(SCHEMA)


def downgrade() -> None:
    op.execute(DOWNGRADE)

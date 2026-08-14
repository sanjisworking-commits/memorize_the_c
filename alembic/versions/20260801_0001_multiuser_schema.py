"""Multi-user personal data schema.

Revision ID: 20260801_0001
Revises:
Create Date: 2026-08-01
"""

from __future__ import annotations

from alembic import op

revision = "20260801_0001"
down_revision = None
branch_labels = None
depends_on = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS user_profile (
    user_id UUID PRIMARY KEY,
    display_name TEXT,
    avatar_url TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS app_session (
    session_id TEXT PRIMARY KEY,
    user_id UUID NOT NULL,
    access_token TEXT NOT NULL,
    refresh_token TEXT NOT NULL,
    csrf_token TEXT NOT NULL,
    display_name TEXT,
    email TEXT,
    phone TEXT,
    avatar_url TEXT,
    provider TEXT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS learning_unit_progress (
    user_id UUID NOT NULL,
    learning_unit_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'new',
    times_completed INTEGER NOT NULL DEFAULT 0,
    last_completed DATE,
    next_revision DATE,
    interval_days INTEGER NOT NULL DEFAULT 0,
    ease_factor DOUBLE PRECISION NOT NULL DEFAULT 2.5,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, learning_unit_id)
);

CREATE TABLE IF NOT EXISTS split_preference (
    user_id UUID NOT NULL,
    parent_clause_id TEXT NOT NULL,
    mode TEXT NOT NULL CHECK (mode IN ('whole', 'letters')),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, parent_clause_id)
);

CREATE TABLE IF NOT EXISTS article_gloss (
    user_id UUID NOT NULL,
    article_number TEXT NOT NULL,
    text TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, article_number)
);

CREATE TABLE IF NOT EXISTS app_settings (
    user_id UUID NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, key)
);

CREATE TABLE IF NOT EXISTS unit_modes_seen (
    user_id UUID NOT NULL,
    learning_unit_id TEXT NOT NULL,
    mode TEXT NOT NULL,
    seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, learning_unit_id, mode)
);

CREATE TABLE IF NOT EXISTS memory_entry (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    title TEXT NOT NULL,
    acronym TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    logged_date DATE NOT NULL,
    status TEXT NOT NULL DEFAULT 'new',
    interval_days INTEGER NOT NULL DEFAULT 0,
    last_completed DATE,
    next_revision DATE,
    times_completed INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS memory_media (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    entry_id UUID NOT NULL REFERENCES memory_entry(id) ON DELETE CASCADE,
    storage_key TEXT NOT NULL,
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (entry_id)
);

CREATE INDEX IF NOT EXISTS idx_progress_user ON learning_unit_progress(user_id);
CREATE INDEX IF NOT EXISTS idx_progress_user_next ON learning_unit_progress(user_id, next_revision);
CREATE INDEX IF NOT EXISTS idx_progress_user_unit ON learning_unit_progress(user_id, learning_unit_id);
CREATE INDEX IF NOT EXISTS idx_modes_user_unit ON unit_modes_seen(user_id, learning_unit_id);
CREATE INDEX IF NOT EXISTS idx_memory_user ON memory_entry(user_id);
CREATE INDEX IF NOT EXISTS idx_memory_user_created ON memory_entry(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_memory_user_next ON memory_entry(user_id, next_revision);
CREATE INDEX IF NOT EXISTS idx_memory_media_user ON memory_media(user_id);
CREATE INDEX IF NOT EXISTS idx_session_user ON app_session(user_id);
"""


def upgrade() -> None:
    op.execute(SCHEMA)


def downgrade() -> None:
    op.execute(
        """
        DROP TABLE IF EXISTS memory_media;
        DROP TABLE IF EXISTS memory_entry;
        DROP TABLE IF EXISTS unit_modes_seen;
        DROP TABLE IF EXISTS app_settings;
        DROP TABLE IF EXISTS article_gloss;
        DROP TABLE IF EXISTS split_preference;
        DROP TABLE IF EXISTS learning_unit_progress;
        DROP TABLE IF EXISTS app_session;
        DROP TABLE IF EXISTS user_profile;
        """
    )

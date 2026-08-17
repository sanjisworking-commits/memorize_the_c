"""Free-Article entitlement slots (3 permanent Articles per Free account).

Revision ID: 20260816_0004
Revises: 20260810_0003
Create Date: 2026-08-16
"""

from __future__ import annotations

from alembic import op

revision = "20260816_0004"
down_revision = "20260810_0003"
branch_labels = None
depends_on = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS user_free_articles (
    user_id TEXT NOT NULL,
    article_number TEXT NOT NULL,
    claimed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, article_number)
);

CREATE INDEX IF NOT EXISTS idx_free_articles_user ON user_free_articles(user_id);
"""


def upgrade() -> None:
    op.execute(SCHEMA)


def downgrade() -> None:
    op.execute(
        """
        DROP INDEX IF EXISTS idx_free_articles_user;
        DROP TABLE IF EXISTS user_free_articles;
        """
    )

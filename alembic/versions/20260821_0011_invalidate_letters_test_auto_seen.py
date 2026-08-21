"""Invalidate visit-generated Letters and Test auto-seen rows.

After gated-completion v1, Letters and Test were still marked complete by
opening the tab. Spoken Letters and /quiz-only Test must not inherit those
rows. unit_modes_seen is current-cycle state, so this only affects cycles
in progress at rollout.

Revision ID: 20260821_0011
Revises: 20260820_0010
Create Date: 2026-08-20
"""

from __future__ import annotations

from alembic import op

revision = "20260821_0011"
down_revision = "20260820_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "DELETE FROM unit_modes_seen WHERE mode IN ('letters', 'test')"
    )


def downgrade() -> None:
    # No-op: the deleted marks were unearned under the new gates.
    pass

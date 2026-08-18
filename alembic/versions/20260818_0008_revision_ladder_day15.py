"""Constitution ladder correction: Day 14 rung becomes Day 15.

Re-slots interval_days 14 -> 15 so a unit currently on the two-week rung
advances to 30 next time instead of repeating the corrected 15 rung.
Stored next_revision dates are deliberately untouched — already-scheduled
reviews keep their dates. The Memory-log ladder (1-3-7-14-30) is a separate
system and is NOT changed.

Revision ID: 20260818_0008
Revises: 20260818_0007
Create Date: 2026-08-18
"""

from __future__ import annotations

from alembic import op

revision = "20260818_0008"
down_revision = "20260818_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE learning_unit_progress SET interval_days = 15 WHERE interval_days = 14"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE learning_unit_progress SET interval_days = 14 WHERE interval_days = 15"
    )

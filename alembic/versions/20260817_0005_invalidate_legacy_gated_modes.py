"""Strict migration for gated Learn-mode completion.

Before the gated-completion model, merely opening Cloze/Type/Recite/Card
wrote a unit_modes_seen row, so cycles in progress at rollout carry unearned
checkmarks — and 'card' is retired outright (replaced by the server-graded
'test' mode, which must never inherit card rows). unit_modes_seen is
current-cycle state (cleared on every Done), so this only affects in-progress
cycles; learners simply redo the gated modes. Read/Letters marks survive.

Revision ID: 20260817_0005
Revises: 20260816_0004
Create Date: 2026-08-17
"""

from __future__ import annotations

from alembic import op

revision = "20260817_0005"
down_revision = "20260816_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "DELETE FROM unit_modes_seen "
        "WHERE mode IN ('cloze', 'type', 'recite', 'card')"
    )


def downgrade() -> None:
    # No-op by design: the deleted marks were unearned under the gated model
    # and cannot be reconstructed; nothing depends on their presence.
    pass

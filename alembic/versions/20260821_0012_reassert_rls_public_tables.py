"""Re-assert Row Level Security on the public tables.

Revision ID: 20260821_0012
Revises: 20260821_0011
Create Date: 2026-08-21

Insurance against an id collision, not new policy.

``20260820_0010`` was claimed twice: by the RLS fix on ``main`` (PR #138) and,
independently, by the Letters/Test invalidation on the Letters branch. Git
merged the two files without a conflict because they are separate paths, and
the collision only surfaced as "two heads under one id" when Alembic read the
directory. The Letters copy has since been renumbered to ``20260821_0011``,
so ``20260820_0010`` now means the RLS migration everywhere.

That leaves one environment-dependent hazard: anywhere that recorded
``20260820_0010`` while it still meant the *Letters* migration, Alembic now
reads that stamp as "RLS already applied" and will never run it. The failure
is silent, and what gets skipped is a security fix — the ``public`` schema is
served to the ``anon`` role through PostgREST.

Rather than depend on inspecting each environment's ``alembic_version`` row,
this migration simply re-asserts the desired end state. Every statement is
``ALTER TABLE IF EXISTS ... ENABLE ROW LEVEL SECURITY``: idempotent, a no-op
where RLS is already on (the overwhelmingly likely case, since ``main`` is
what deploys), a no-op for tables absent in a given environment, and the
actual repair anywhere the stamp collided. No policies are created, so app
queries — which connect as the table-owning ``postgres`` role and bypass RLS
— are unaffected either way.

Deliberately has no downgrade: 0010 already owns disabling these tables, and
re-disabling them here would be a security regression, not a rollback.
"""

from __future__ import annotations

from alembic import op

revision = "20260821_0012"
down_revision = "20260821_0011"
branch_labels = None
depends_on = None

# Kept identical to 0010's list on purpose: this is the same end state,
# re-applied. If a table is added to that list, add it here too.
TABLES = (
    "user_profile",
    "app_session",
    "learning_unit_progress",
    "split_preference",
    "article_gloss",
    "app_settings",
    "unit_modes_seen",
    "memory_entry",
    "memory_media",
    "user_free_articles",
    "billing_orders",
    "google_calendar_connections",
    "google_calendar_events",
    "alembic_version",
)


def upgrade() -> None:
    for table in TABLES:
        op.execute(f"ALTER TABLE IF EXISTS {table} ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    # No-op: see the module docstring. Disabling RLS belongs to 0010's
    # downgrade; repeating it here would silently widen exposure.
    pass

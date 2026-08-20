"""Enable Row Level Security on the remaining public tables.

Revision ID: 20260820_0010
Revises: 20260819_0009
Create Date: 2026-08-20

The Supabase database linter flags every table in the ``public`` schema that
does not have RLS enabled (``0013_rls_disabled_in_public``), and additionally
``app_session`` for exposing ``access_token`` / ``refresh_token`` /
``session_id`` (``0023_sensitive_columns_exposed``). Supabase serves the
``public`` schema through PostgREST to the ``anon`` / ``authenticated`` roles,
so any such table is reachable by anyone holding the project's anon key.

This application does **not** use the Supabase Data API (PostgREST) at all — it
talks to Postgres directly via ``DATABASE_URL`` (psycopg) as the table-owning
``postgres`` role, which bypasses RLS. So enabling RLS with no policies leaves
every app query untouched while making the Data API return zero rows for these
tables. This mirrors the fix already applied to newer tables in migrations
0002 (issue_reports), 0003 (contact_messages) and 0006 (user_roles /
access_grants / admin_audit_log) — which is exactly why those tables are not in
the linter report.

The tables covered here are the ones created before the pattern existed: the
base multi-user schema (0001), ``user_free_articles`` (0004), ``billing_orders``
(0007), the Google Calendar tables (0009), and Alembic's own bookkeeping table.
``IF EXISTS`` keeps it a no-op for any table absent in a given environment, and
re-enabling an already-enabled table is harmless.
"""

from __future__ import annotations

from alembic import op

revision = "20260820_0010"
down_revision = "20260819_0009"
branch_labels = None
depends_on = None

SCHEMA = """
ALTER TABLE IF EXISTS user_profile ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS app_session ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS learning_unit_progress ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS split_preference ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS article_gloss ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS app_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS unit_modes_seen ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS memory_entry ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS memory_media ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS user_free_articles ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS billing_orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS google_calendar_connections ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS google_calendar_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS alembic_version ENABLE ROW LEVEL SECURITY;
"""

DOWNGRADE = """
ALTER TABLE IF EXISTS user_profile DISABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS app_session DISABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS learning_unit_progress DISABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS split_preference DISABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS article_gloss DISABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS app_settings DISABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS unit_modes_seen DISABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS memory_entry DISABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS memory_media DISABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS user_free_articles DISABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS billing_orders DISABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS google_calendar_connections DISABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS google_calendar_events DISABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS alembic_version DISABLE ROW LEVEL SECURITY;
"""


def upgrade() -> None:
    op.execute(SCHEMA)


def downgrade() -> None:
    op.execute(DOWNGRADE)

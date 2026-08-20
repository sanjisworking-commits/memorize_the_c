"""Guard: every public table a migration creates has RLS enabled somewhere in
the Alembic migration set (text scan, no live DB).

Regression lock for the Supabase linter findings 0013_rls_disabled_in_public
and 0023_sensitive_columns_exposed: Supabase serves the ``public`` schema over
PostgREST to the ``anon`` / ``authenticated`` roles, so any table without RLS is
reachable by anyone holding the project anon key. The app never uses the Data
API — it connects directly as the owning ``postgres`` role (which bypasses RLS)
— so enabling RLS with no policies is invisible to the app and closes the hole.
This test keeps future tables from shipping without the same treatment.
"""

from __future__ import annotations

import re
from pathlib import Path

VERSIONS = Path(__file__).resolve().parents[1] / "alembic" / "versions"

_CREATE_RE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([a-z_][a-z0-9_]*)", re.IGNORECASE
)
_RLS_RE = re.compile(
    r"ALTER\s+TABLE\s+(?:IF\s+EXISTS\s+)?([a-z_][a-z0-9_]*)\s+ENABLE\s+ROW\s+LEVEL\s+SECURITY",
    re.IGNORECASE,
)

# Tables the Supabase linter reported as RLS-disabled (plus split_preference,
# a public table from the same base schema that predates the RLS pattern).
_LINTER_FLAGGED = {
    "app_session",
    "learning_unit_progress",
    "article_gloss",
    "app_settings",
    "user_profile",
    "unit_modes_seen",
    "memory_entry",
    "memory_media",
    "user_free_articles",
    "google_calendar_connections",
    "billing_orders",
    "google_calendar_events",
    "split_preference",
}


def _scan() -> tuple[set[str], set[str]]:
    created: set[str] = set()
    rls: set[str] = set()
    for path in VERSIONS.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        created |= {m.lower() for m in _CREATE_RE.findall(text)}
        rls |= {m.lower() for m in _RLS_RE.findall(text)}
    return created, rls


def test_every_created_public_table_has_rls_enabled():
    created, rls = _scan()
    missing = sorted(created - rls)
    assert not missing, (
        "These public tables are created by a migration but never get "
        f"ENABLE ROW LEVEL SECURITY: {missing}. Add it (owner role bypasses RLS, "
        "so app queries are unaffected) or the Supabase linter will flag them."
    )


def test_linter_flagged_tables_now_have_rls():
    _, rls = _scan()
    missing = sorted(_LINTER_FLAGGED - rls)
    assert not missing, f"Linter-flagged tables still missing RLS: {missing}"

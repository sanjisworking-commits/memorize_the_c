"""Issue reports V1 schema: constants + Alembic migration (no live DB)."""

from __future__ import annotations

import ast
import re
from pathlib import Path

from constitution_memorizer.reports import (
    DEFAULT_ISSUE_STATUS,
    ISSUE_STATUSES,
    ISSUE_TYPES,
)

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "alembic" / "versions" / "20260810_0002_issue_reports.py"
PRIOR = ROOT / "alembic" / "versions" / "20260801_0001_multiuser_schema.py"


def _load_migration_source() -> str:
    assert MIGRATION.is_file(), f"missing migration: {MIGRATION}"
    return MIGRATION.read_text(encoding="utf-8")


def _schema_sql(source: str) -> str:
    match = re.search(r'SCHEMA\s*=\s*"""(.*?)"""', source, re.DOTALL)
    assert match is not None, "SCHEMA triple-quoted string not found"
    return match.group(1)


def test_issue_type_and_status_constants():
    assert ISSUE_TYPES == {
        "incorrect_fact",
        "outdated_information",
        "interpretation_issue",
        "typo",
        "source_issue",
        "other",
    }
    assert ISSUE_STATUSES == {"new", "reviewing", "fixed", "rejected"}
    assert DEFAULT_ISSUE_STATUS == "new"
    assert DEFAULT_ISSUE_STATUS in ISSUE_STATUSES


def test_migration_revision_chain():
    source = _load_migration_source()
    tree = ast.parse(source)
    revision = None
    down_revision = None
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "revision":
                    revision = ast.literal_eval(node.value)
                if isinstance(target, ast.Name) and target.id == "down_revision":
                    down_revision = ast.literal_eval(node.value)
    assert revision == "20260810_0002"
    assert down_revision == "20260801_0001"
    assert PRIOR.is_file()
    prior = PRIOR.read_text(encoding="utf-8")
    assert 'revision = "20260801_0001"' in prior


def test_migration_schema_columns_defaults_checks_indexes_and_rls():
    sql = _schema_sql(_load_migration_source())
    compact = " ".join(sql.split())

    assert "CREATE TABLE IF NOT EXISTS issue_reports" in compact
    for col in (
        "article_number TEXT NULL",
        "section TEXT NULL",
        "selected_text TEXT NULL",
        "issue_type TEXT NOT NULL",
        "description TEXT NOT NULL",
        "suggested_correction TEXT NULL",
        "source_url TEXT NULL",
        "reporter_email TEXT NULL",
        "page_url TEXT NOT NULL",
        "status TEXT NOT NULL DEFAULT 'new'",
        "created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()",
    ):
        assert col in compact, f"missing column definition: {col}"

    assert "id UUID PRIMARY KEY DEFAULT gen_random_uuid()" in compact

    for issue_type in ISSUE_TYPES:
        assert f"'{issue_type}'" in sql
    for status in ISSUE_STATUSES:
        assert f"'{status}'" in sql
    assert "issue_reports_issue_type_check" in sql
    assert "issue_reports_status_check" in sql

    assert "idx_issue_reports_status" in sql
    assert "idx_issue_reports_article_number" in sql
    assert "idx_issue_reports_created_at" in sql

    assert "ALTER TABLE issue_reports ENABLE ROW LEVEL SECURITY" in compact
    # V1: no anon/authenticated policies — server role bypasses RLS.
    assert "CREATE POLICY" not in sql.upper()


def test_migration_downgrade_drops_table():
    source = _load_migration_source()
    assert "def downgrade" in source
    assert "DROP TABLE IF EXISTS issue_reports" in source
    assert "DROP INDEX IF EXISTS idx_issue_reports_status" in source

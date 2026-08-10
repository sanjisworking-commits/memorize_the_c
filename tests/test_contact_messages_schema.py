"""contact_messages Alembic migration shape (no live DB)."""

from __future__ import annotations

from pathlib import Path

from constitution_memorizer.reports.contact_constants import (
    CONTACT_STATUSES,
    CONTACT_TOPICS,
    DEFAULT_CONTACT_STATUS,
)

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "alembic/versions/20260810_0003_contact_messages.py"


def test_contact_constants():
    assert DEFAULT_CONTACT_STATUS == "new"
    assert "technical_issue" in CONTACT_TOPICS
    assert "resolved" in CONTACT_STATUSES


def test_migration_sql_has_checks_and_rls():
    text = MIGRATION.read_text(encoding="utf-8")
    assert 'revision = "20260810_0003"' in text
    assert 'down_revision = "20260810_0002"' in text
    assert "CREATE TABLE IF NOT EXISTS contact_messages" in text
    assert "technical_issue" in text
    assert "general_feedback" in text
    assert "feature_suggestion" in text
    assert "ENABLE ROW LEVEL SECURITY" in text
    assert "idx_contact_messages_status" in text

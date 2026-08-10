"""Contact Us topic/status constants (keep in sync with Alembic CHECKs)."""

from __future__ import annotations

CONTACT_TOPICS: frozenset[str] = frozenset(
    (
        "technical_issue",
        "general_feedback",
        "feature_suggestion",
        "other",
    )
)

CONTACT_STATUSES: frozenset[str] = frozenset(
    (
        "new",
        "reviewing",
        "resolved",
    )
)

DEFAULT_CONTACT_STATUS = "new"

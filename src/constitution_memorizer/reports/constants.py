"""Domain constants for the Report-an-issue feature (V1)."""

from __future__ import annotations

# Keep in sync with CHECK constraints on issue_reports.issue_type.
ISSUE_TYPES: frozenset[str] = frozenset(
    {
        "incorrect_fact",
        "outdated_information",
        "interpretation_issue",
        "typo",
        "source_issue",
        "other",
    }
)

# Keep in sync with CHECK constraints on issue_reports.status.
ISSUE_STATUSES: frozenset[str] = frozenset(
    {
        "new",
        "reviewing",
        "fixed",
        "rejected",
    }
)

DEFAULT_ISSUE_STATUS = "new"

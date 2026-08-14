"""Canonical user id helpers for progress repositories."""

from __future__ import annotations

from uuid import UUID

# Implicit single-tenant / legacy local user used when multi-user auth is off.
LOCAL_USER_ID = UUID("00000000-0000-4000-8000-000000000001")


def as_user_id(value: UUID | str) -> str:
    """Normalize a user id to the string form stored in SQLite/Postgres."""
    return str(value)

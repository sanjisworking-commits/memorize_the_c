"""Auth domain models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class AuthenticatedUser:
    """Canonical application user derived from Supabase Auth."""

    id: UUID
    email: str | None
    phone: str | None
    display_name: str | None
    avatar_url: str | None
    provider: str


@dataclass(frozen=True)
class AuthenticatedSession:
    """Tokens returned by the auth provider after a successful login."""

    user: AuthenticatedUser
    access_token: str
    refresh_token: str
    expires_at: datetime | None = None

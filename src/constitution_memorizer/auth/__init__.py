"""Authentication package for the multi-user hosted app."""

from constitution_memorizer.auth.models import AuthenticatedSession, AuthenticatedUser
from constitution_memorizer.auth.exceptions import (
    AuthConfigError,
    AuthError,
    InvalidCredentialsError,
    RateLimitError,
    SessionExpiredError,
)

__all__ = [
    "AuthConfigError",
    "AuthError",
    "AuthenticatedSession",
    "AuthenticatedUser",
    "InvalidCredentialsError",
    "RateLimitError",
    "SessionExpiredError",
]

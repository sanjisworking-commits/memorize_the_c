"""Auth-related exceptions."""

from __future__ import annotations


class AuthError(Exception):
    """Base authentication error."""


class AuthConfigError(AuthError):
    """Invalid or incomplete authentication configuration."""


class InvalidCredentialsError(AuthError):
    """OTP, token, or OAuth callback validation failed."""


class OtpExpiredError(InvalidCredentialsError):
    """OTP was rejected because it has expired (distinct from incorrect)."""


class SessionExpiredError(AuthError):
    """Server session is missing, expired, or revoked."""


class RateLimitError(AuthError):
    """OTP or auth endpoint rate limit exceeded."""

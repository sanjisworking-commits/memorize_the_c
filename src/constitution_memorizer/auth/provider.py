"""Authentication provider protocol."""

from __future__ import annotations

from typing import Protocol

from constitution_memorizer.auth.models import AuthenticatedSession, AuthenticatedUser


class AuthProvider(Protocol):
    """Provider-agnostic authentication operations."""

    def get_google_authorization_url(
        self,
        redirect_url: str,
        *,
        state: str,
        code_challenge: str | None = None,
        code_challenge_method: str = "S256",
    ) -> str:
        """Return the Google OAuth authorization URL (with state/PKCE as supported)."""
        ...

    def exchange_oauth_callback(
        self,
        *,
        code: str | None,
        access_token: str | None,
        refresh_token: str | None,
        redirect_url: str,
        code_verifier: str | None = None,
    ) -> AuthenticatedSession:
        """Complete an OAuth redirect and return a session."""
        ...

    def send_phone_otp(self, phone_number: str) -> None:
        """Request an SMS OTP for an E.164 phone number."""
        ...

    def verify_phone_otp(self, phone_number: str, otp: str) -> AuthenticatedSession:
        """Verify an SMS OTP and return a session."""
        ...

    def verify_access_token(self, access_token: str) -> AuthenticatedUser:
        """Validate an access token and return the authenticated user."""
        ...

    def refresh_session(self, refresh_token: str) -> AuthenticatedSession:
        """Refresh an expired access token."""
        ...

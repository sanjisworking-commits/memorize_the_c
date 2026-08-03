"""In-memory auth provider for automated tests (no Google/SMS)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from constitution_memorizer.auth.exceptions import (
    InvalidCredentialsError,
    OtpExpiredError,
)
from constitution_memorizer.auth.models import AuthenticatedSession, AuthenticatedUser
from constitution_memorizer.auth.phone import normalize_e164


class FakeAuthProvider:
    """Deterministic AuthProvider used by the unit/integration test suite."""

    def __init__(self) -> None:
        self.google_users: dict[str, AuthenticatedUser] = {}
        self.phone_users: dict[str, AuthenticatedUser] = {}
        self.pending_otps: dict[str, str] = {}
        self.tokens: dict[str, AuthenticatedUser] = {}
        self.refresh_tokens: dict[str, str] = {}
        self.sent_otps: list[str] = []
        self.oauth_states: set[str] = set()

    def seed_google_user(
        self,
        *,
        user_id: UUID | None = None,
        email: str = "user@example.com",
        display_name: str = "Test User",
        avatar_url: str | None = "https://example.com/a.png",
    ) -> AuthenticatedUser:
        user = AuthenticatedUser(
            id=user_id or uuid4(),
            email=email,
            phone=None,
            display_name=display_name,
            avatar_url=avatar_url,
            provider="google",
        )
        self.google_users[email] = user
        return user

    def seed_phone_user(
        self,
        *,
        phone: str,
        user_id: UUID | None = None,
        display_name: str | None = None,
    ) -> AuthenticatedUser:
        normalized = normalize_e164(phone)
        user = AuthenticatedUser(
            id=user_id or uuid4(),
            email=None,
            phone=normalized,
            display_name=display_name,
            avatar_url=None,
            provider="phone",
        )
        self.phone_users[normalized] = user
        return user

    def get_google_authorization_url(
        self,
        redirect_url: str,
        *,
        state: str,
        code_challenge: str | None = None,
        code_challenge_method: str = "S256",
    ) -> str:
        del code_challenge, code_challenge_method
        self.oauth_states.add(state)
        return f"{redirect_url}?state={state}&code=fake-google-code"

    def exchange_oauth_callback(
        self,
        *,
        code: str | None,
        access_token: str | None,
        refresh_token: str | None,
        redirect_url: str,
        code_verifier: str | None = None,
    ) -> AuthenticatedSession:
        del redirect_url, access_token, refresh_token, code_verifier
        if code != "fake-google-code":
            raise InvalidCredentialsError("Invalid OAuth code")
        user = next(iter(self.google_users.values()), None)
        if user is None:
            user = self.seed_google_user()
        return self._issue(user)

    def send_phone_otp(self, phone_number: str) -> None:
        normalized = normalize_e164(phone_number)
        self.pending_otps[normalized] = "123456"
        self.sent_otps.append(normalized)
        if normalized not in self.phone_users:
            self.seed_phone_user(phone=normalized)

    def verify_phone_otp(self, phone_number: str, otp: str) -> AuthenticatedSession:
        """Demo OTP codes (local FakeAuthProvider only): 123456 ok, 000000 expired."""
        normalized = normalize_e164(phone_number)
        code = (otp or "").strip()
        if code == "000000":
            raise OtpExpiredError("This code has expired")
        expected = self.pending_otps.get(normalized)
        if expected is None or code != expected:
            raise InvalidCredentialsError("Invalid code")
        user = self.phone_users.get(normalized)
        if user is None:
            user = self.seed_phone_user(phone=normalized)
        del self.pending_otps[normalized]
        return self._issue(user)

    def verify_access_token(self, access_token: str) -> AuthenticatedUser:
        user = self.tokens.get(access_token)
        if user is None:
            raise InvalidCredentialsError("Invalid access token")
        return user

    def refresh_session(self, refresh_token: str) -> AuthenticatedSession:
        access = self.refresh_tokens.get(refresh_token)
        if access is None:
            raise InvalidCredentialsError("Invalid refresh token")
        user = self.tokens.get(access)
        if user is None:
            raise InvalidCredentialsError("Invalid refresh token")
        return self._issue(user)

    def _issue(self, user: AuthenticatedUser) -> AuthenticatedSession:
        access = f"access-{user.id}-{uuid4().hex[:8]}"
        refresh = f"refresh-{user.id}-{uuid4().hex[:8]}"
        self.tokens[access] = user
        self.refresh_tokens[refresh] = access
        return AuthenticatedSession(
            user=user,
            access_token=access,
            refresh_token=refresh,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )

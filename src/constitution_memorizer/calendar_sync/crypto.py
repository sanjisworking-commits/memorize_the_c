"""Sealing for Google refresh tokens (Fernet, key from GCAL_TOKEN_KEY).

Refresh tokens are long-lived offline credentials, so unlike the short-lived
Supabase session tokens they are never stored in the clear. The key's
absence disables the whole calendar feature rather than degrading to
plaintext storage.
"""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken


class TokenSealError(RuntimeError):
    """Raised when a stored token cannot be unsealed (wrong/rotated key)."""


class TokenSealer:
    def __init__(self, key: str) -> None:
        self._fernet = Fernet(key.encode("utf-8"))

    def seal(self, token: str) -> str:
        return self._fernet.encrypt(token.encode("utf-8")).decode("utf-8")

    def unseal(self, sealed: str) -> str:
        try:
            return self._fernet.decrypt(sealed.encode("utf-8")).decode("utf-8")
        except InvalidToken as exc:
            raise TokenSealError("Stored Google token cannot be unsealed") from exc

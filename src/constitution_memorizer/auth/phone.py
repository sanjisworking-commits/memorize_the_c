"""Phone number helpers (E.164)."""

from __future__ import annotations

import re

from constitution_memorizer.auth.exceptions import InvalidCredentialsError

_E164_RE = re.compile(r"^\+[1-9]\d{7,14}$")


def normalize_e164(phone: str) -> str:
    """Normalize and validate an E.164 phone number. Does not guess country codes."""
    cleaned = "".join(phone.split())
    if cleaned.startswith("00"):
        cleaned = "+" + cleaned[2:]
    if not _E164_RE.match(cleaned):
        raise InvalidCredentialsError(
            "Enter a full phone number in E.164 format, e.g. +919876543210"
        )
    return cleaned


def mask_phone(phone: str) -> str:
    """Mask a phone number for logs and UI, e.g. +91******3210."""
    if len(phone) < 8:
        return "***"
    return phone[:3] + ("*" * max(4, len(phone) - 7)) + phone[-4:]

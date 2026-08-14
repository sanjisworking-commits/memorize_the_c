"""Phone number helpers (India UI + E.164 for Supabase)."""

from __future__ import annotations

import re

from constitution_memorizer.auth.exceptions import InvalidCredentialsError

_E164_RE = re.compile(r"^\+[1-9]\d{7,14}$")
_INDIA_MOBILE_RE = re.compile(r"^[6-9]\d{9}$")


def normalize_india_mobile(phone: str) -> str:
    """
    Accept a 10-digit Indian mobile (optionally with +91 / 91 / 0 prefix)
    and return E.164 (+91XXXXXXXXXX).
    """
    cleaned = "".join(ch for ch in phone if ch.isdigit() or ch == "+")
    if cleaned.startswith("+91"):
        digits = cleaned[3:]
    elif cleaned.startswith("91") and len(cleaned) >= 12:
        digits = cleaned[2:]
    elif cleaned.startswith("0") and len(cleaned) == 11:
        digits = cleaned[1:]
    else:
        digits = cleaned.lstrip("+")
    if not _INDIA_MOBILE_RE.match(digits):
        raise InvalidCredentialsError(
            "Enter a valid 10-digit Indian mobile number starting with 6–9."
        )
    return f"+91{digits}"


def normalize_e164(phone: str) -> str:
    """
    Normalize to E.164.

    India-looking input (+91 / 10-digit / 0-prefixed) is validated as an
    Indian mobile. Other full E.164 values are accepted as-is.
    """
    cleaned = "".join(phone.split())
    if cleaned.startswith("00"):
        cleaned = "+" + cleaned[2:]
    digits = "".join(ch for ch in cleaned if ch.isdigit())
    india_like = (
        cleaned.startswith("+91")
        or (cleaned.startswith("91") and len(digits) >= 12)
        or (cleaned.startswith("0") and len(digits) == 11)
        or (cleaned.isdigit() and len(cleaned) == 10)
    )
    if india_like:
        return normalize_india_mobile(cleaned)
    if not _E164_RE.match(cleaned):
        raise InvalidCredentialsError(
            "Enter a valid 10-digit Indian mobile number, or full E.164 like +919876543210."
        )
    return cleaned


def mask_phone(phone: str) -> str:
    """Mask a phone number for logs and UI, e.g. +91******3210."""
    if len(phone) < 8:
        return "***"
    return phone[:3] + ("*" * max(4, len(phone) - 7)) + phone[-4:]


def display_national(phone: str) -> str:
    """Return national 10-digit form for +91 numbers, else the raw value."""
    if phone.startswith("+91") and len(phone) == 13:
        return phone[3:]
    return phone

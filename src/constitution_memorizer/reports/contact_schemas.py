"""Pydantic request/response models for Contact Us API."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from constitution_memorizer.reports.contact_constants import CONTACT_TOPICS


def _strip_optional(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped if stripped else None


def _is_plausible_email(value: str) -> bool:
    if value.count("@") != 1:
        return False
    local, domain = value.split("@", 1)
    if not local or not domain:
        return False
    if " " in local or " " in domain:
        return False
    if "." not in domain:
        return False
    if domain.startswith(".") or domain.endswith("."):
        return False
    return True


class ContactMessageRequest(BaseModel):
    """JSON body for POST /api/contact."""

    model_config = ConfigDict(str_strip_whitespace=False, extra="forbid")

    topic: str = Field(..., min_length=1, max_length=64)
    message: str = Field(..., max_length=8000)
    page_url: str | None = Field(default=None, max_length=2000)
    reporter_email: str | None = Field(default=None, max_length=254)
    # Transient Turnstile token — never persisted or emailed.
    turnstile_token: str | None = Field(default=None, max_length=2048)

    @field_validator("topic")
    @classmethod
    def validate_topic(cls, value: str) -> str:
        cleaned = value.strip()
        if cleaned not in CONTACT_TOPICS:
            raise ValueError(
                "topic must be one of: " + ", ".join(sorted(CONTACT_TOPICS))
            )
        return cleaned

    @field_validator("message")
    @classmethod
    def required_non_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("must not be blank")
        return cleaned

    @field_validator("page_url", "turnstile_token", mode="before")
    @classmethod
    def optional_blank_to_none(cls, value: Any) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("must be a string")
        return _strip_optional(value)

    @field_validator("reporter_email", mode="before")
    @classmethod
    def validate_reporter_email(cls, value: Any) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("must be a string")
        cleaned = value.strip()
        if not cleaned:
            return None
        if len(cleaned) > 254:
            raise ValueError("must be at most 254 characters")
        if not _is_plausible_email(cleaned):
            raise ValueError("must look like a valid email address")
        return cleaned


class ContactMessageResponse(BaseModel):
    success: bool = True
    message_id: UUID
    status: str

"""Multi-user application settings loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from constitution_memorizer.auth.exceptions import AuthConfigError

AppEnv = Literal["development", "staging", "production", "test"]


class MultiUserSettings(BaseSettings):
    """Hosted multi-user configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: AppEnv = Field(default="development", alias="APP_ENV")
    app_base_url: str = Field(default="http://127.0.0.1:8010", alias="APP_BASE_URL")
    port: int = Field(default=8010, alias="PORT")

    database_url: str = Field(default="", alias="DATABASE_URL")
    supabase_url: str = Field(default="", alias="SUPABASE_URL")
    supabase_anon_key: str = Field(default="", alias="SUPABASE_ANON_KEY")
    session_secret: str = Field(default="", alias="SESSION_SECRET")

    auth_google_enabled: bool = Field(default=True, alias="AUTH_GOOGLE_ENABLED")
    auth_phone_enabled: bool = Field(default=True, alias="AUTH_PHONE_ENABLED")
    cookie_secure: bool = Field(default=False, alias="COOKIE_SECURE")

    # CAPTCHA integration point (optional; validated only when enabled).
    captcha_enabled: bool = Field(default=False, alias="CAPTCHA_ENABLED")
    captcha_secret: str = Field(default="", alias="CAPTCHA_SECRET")

    multiuser_enabled: bool = Field(default=False, alias="MULTIUSER_ENABLED")

    @field_validator(
        "auth_google_enabled",
        "auth_phone_enabled",
        "cookie_secure",
        "captcha_enabled",
        "multiuser_enabled",
        mode="before",
    )
    @classmethod
    def _parse_bool(cls, value: object) -> object:
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"1", "true", "yes", "on"}:
                return True
            if lowered in {"0", "false", "no", "off"}:
                return False
        return value

    def validate_for_startup(self) -> None:
        """Raise AuthConfigError when staging/production config is incomplete."""
        if self.app_env in {"staging", "production"}:
            if not self.auth_google_enabled and not self.auth_phone_enabled:
                raise AuthConfigError(
                    "At least one of AUTH_GOOGLE_ENABLED or AUTH_PHONE_ENABLED "
                    "must be true in staging/production."
                )
            missing = [
                name
                for name, val in (
                    ("DATABASE_URL", self.database_url),
                    ("SUPABASE_URL", self.supabase_url),
                    ("SUPABASE_ANON_KEY", self.supabase_anon_key),
                    ("SESSION_SECRET", self.session_secret),
                )
                if not val
            ]
            if missing:
                raise AuthConfigError(
                    "Missing required multi-user settings: " + ", ".join(missing)
                )
            if self.captcha_enabled and not self.captcha_secret:
                raise AuthConfigError(
                    "CAPTCHA_SECRET is required when CAPTCHA_ENABLED=true"
                )


@lru_cache(maxsize=1)
def get_multiuser_settings() -> MultiUserSettings:
    return MultiUserSettings()


def clear_settings_cache() -> None:
    get_multiuser_settings.cache_clear()

"""Multi-user application settings loaded from environment variables."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from constitution_memorizer.auth.exceptions import AuthConfigError

AppEnv = Literal["development", "staging", "production", "test"]


def load_env_file(path: Path | str | None = None, *, override: bool = False) -> Path | None:
    """
    Load KEY=VALUE pairs from a .env file into os.environ.

    Does not override existing non-empty environment variables unless override=True.
    Returns the path loaded, or None if no file was found.
    """
    candidates: list[Path] = []
    if path is not None:
        candidates.append(Path(path))
    else:
        cwd = Path.cwd() / ".env"
        candidates.append(cwd)
        # Also try repo-root-ish relative to this package (…/memorize_the_c/.env)
        pkg_root = Path(__file__).resolve().parents[3]
        candidates.append(pkg_root / ".env")

    env_path = next((p for p in candidates if p.is_file()), None)
    if env_path is None:
        return None

    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        if not key:
            continue
        if override or key not in os.environ or os.environ.get(key, "") == "":
            os.environ[key] = value
    return env_path


class MultiUserSettings(BaseSettings):
    """Hosted multi-user configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
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

    def validate_for_startup(self, *, require_secrets: bool = False) -> None:
        """Raise AuthConfigError when multi-user config is incomplete."""
        staging = self.app_env in {"staging", "production"}
        if staging:
            require_secrets = True
            if not self.auth_google_enabled and not self.auth_phone_enabled:
                raise AuthConfigError(
                    "At least one of AUTH_GOOGLE_ENABLED or AUTH_PHONE_ENABLED "
                    "must be true in staging/production."
                )
        if not require_secrets:
            return

        required: list[tuple[str, str]] = [
            ("SUPABASE_URL", self.supabase_url),
            ("SUPABASE_ANON_KEY", self.supabase_anon_key),
            ("SESSION_SECRET", self.session_secret),
        ]
        if staging:
            required.insert(0, ("DATABASE_URL", self.database_url))

        missing = [name for name, val in required if not (val or "").strip()]
        if missing:
            raise AuthConfigError(
                "Missing required multi-user settings: "
                + ", ".join(missing)
                + ". Put them in .env (SUPABASE_URL must be "
                "https://<project-ref>.supabase.co, not the dashboard URL)."
            )
        if "supabase.com/dashboard" in (self.supabase_url or ""):
            raise AuthConfigError(
                "SUPABASE_URL looks like the dashboard link. Use the API URL "
                "instead, e.g. https://YOUR_PROJECT_REF.supabase.co"
            )
        if self.captcha_enabled and not self.captcha_secret:
            raise AuthConfigError(
                "CAPTCHA_SECRET is required when CAPTCHA_ENABLED=true"
            )

    def missing_supabase(self) -> list[str]:
        missing: list[str] = []
        if not (self.supabase_url or "").strip():
            missing.append("SUPABASE_URL")
        if not (self.supabase_anon_key or "").strip():
            missing.append("SUPABASE_ANON_KEY")
        return missing


@lru_cache(maxsize=1)
def get_multiuser_settings() -> MultiUserSettings:
    return MultiUserSettings()


def clear_settings_cache() -> None:
    get_multiuser_settings.cache_clear()

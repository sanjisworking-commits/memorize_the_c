"""ASGI entrypoint for hosted web (no Docling / CLI import)."""

from __future__ import annotations

from constitution_memorizer.multiuser.settings import (
    get_multiuser_settings,
    load_env_file,
)
from constitution_memorizer.web.app import create_app

load_env_file()
settings = get_multiuser_settings()
app = create_app(
    multiuser=settings.multiuser_enabled,
    multiuser_settings=settings,
)

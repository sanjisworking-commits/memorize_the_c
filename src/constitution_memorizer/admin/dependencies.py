"""Request-facing role resolution and the /admin authorization dependency.

Three paths with different staleness guarantees:

- ``require_admin`` / ``resolve_is_admin`` — authoritative DB role lookup,
  memoized only within the request. Used for /admin authorization; revoking
  the role takes effect on the next request.
- ``resolve_access_override`` — one round trip (role + effective grant),
  memoized per request. Feeds the entitlement layer; independent of
  ``ADMIN_ENABLED`` because the paywall bypass follows the role.
- ``admin_hint`` — ~60s TTL cache, cosmetic account-menu link only.
"""

from __future__ import annotations

from datetime import datetime, timezone
from time import perf_counter

from fastapi import HTTPException, Request

from constitution_memorizer.admin.store import AccessOverride
from constitution_memorizer.auth.models import AuthenticatedUser

_UNSET = object()


def _record_timing(stage: str, started: float) -> None:
    from constitution_memorizer.web.request_context import record_request_timing

    record_request_timing(stage, started)


def resolve_is_admin(request: Request) -> bool:
    """Authoritative admin-role check, memoized on request.state."""
    cached = getattr(request.state, "is_admin", None)
    if cached is not None:
        return bool(cached)
    user = getattr(request.state, "current_user", None)
    store = getattr(request.app.state, "access_store", None)
    result = bool(
        getattr(request.app.state, "multiuser_enabled", False)
        and user is not None
        and store is not None
        and store.is_admin(user.id)
    )
    request.state.is_admin = result
    return result


def resolve_access_override(request: Request) -> AccessOverride:
    """Role + effective grant in one memoized round trip per request."""
    cached = getattr(request.state, "access_override", _UNSET)
    if cached is not _UNSET:
        return cached  # type: ignore[return-value]
    user = getattr(request.state, "current_user", None)
    store = getattr(request.app.state, "access_store", None)
    if (
        not getattr(request.app.state, "multiuser_enabled", False)
        or user is None
        or store is None
    ):
        override = AccessOverride()
    else:
        started = perf_counter()
        override = store.resolve_access_override(
            user.id, datetime.now(timezone.utc)
        )
        _record_timing("access_override", started)
    request.state.access_override = override
    # The authoritative bit came along for free; share the memo.
    if getattr(request.state, "is_admin", None) is None:
        request.state.is_admin = override.is_admin
    return override


def admin_hint(request: Request) -> bool:
    """Cosmetic nav-link hint from the TTL cache. Never used to authorize."""
    if not getattr(request.app.state, "admin_enabled", False):
        return False
    user = getattr(request.state, "current_user", None)
    store = getattr(request.app.state, "access_store", None)
    cache = getattr(request.app.state, "admin_hint_cache", None)
    if (
        not getattr(request.app.state, "multiuser_enabled", False)
        or user is None
        or store is None
        or cache is None
    ):
        return False

    def _load() -> bool:
        started = perf_counter()
        value = store.is_admin(user.id)
        _record_timing("admin_hint", started)
        return value

    return cache.get(user.id, _load)


def require_admin(request: Request) -> AuthenticatedUser:
    """Router-wide /admin authorization: authoritative role check per request.

    404 (not 403) for signed-in non-admins, when ADMIN_ENABLED is off, or in
    single-user mode, so the console's existence is not disclosed. Guests get
    a login redirect from the auth middleware before reaching this.
    """
    not_found = HTTPException(status_code=404, detail="Not Found")
    if not getattr(request.app.state, "admin_enabled", False):
        raise not_found
    if not getattr(request.app.state, "multiuser_enabled", False):
        raise not_found
    user = getattr(request.state, "current_user", None)
    if user is None:
        raise not_found
    if not resolve_is_admin(request):
        raise not_found
    return user

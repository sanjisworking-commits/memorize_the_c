"""FastAPI dependencies for authentication."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse

from constitution_memorizer.auth.exceptions import SessionExpiredError
from constitution_memorizer.auth.models import AuthenticatedUser
from constitution_memorizer.auth.sessions import (
    CSRF_COOKIE_NAME,
    SESSION_COOKIE_NAME,
    SessionStore,
    require_session,
)


def _session_store(request: Request) -> SessionStore:
    return request.app.state.session_store


def get_optional_current_user(request: Request) -> AuthenticatedUser | None:
    store: SessionStore = request.app.state.session_store
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_id:
        return None
    session = store.get(session_id)
    if session is None:
        return None
    request.state.auth_session = session
    return session.user


def require_current_user(request: Request) -> AuthenticatedUser:
    user = get_optional_current_user(request)
    if user is None:
        raise HTTPException(
            status_code=303,
            detail="Authentication required",
            headers={"Location": "/login"},
        )
    return user


def require_csrf(request: Request, csrf_token: str | None = Form(default=None)) -> None:
    """Validate CSRF for state-changing form posts."""
    session = getattr(request.state, "auth_session", None)
    if session is None:
        # Allow login routes to validate via cookie pair before session exists.
        cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
        form_token = csrf_token
        if not cookie_token or not form_token or cookie_token != form_token:
            raise HTTPException(status_code=403, detail="CSRF validation failed")
        return
    form_token = csrf_token or request.headers.get("X-CSRF-Token")
    if not form_token or form_token != session.csrf_token:
        raise HTTPException(status_code=403, detail="CSRF validation failed")


CurrentUser = Annotated[AuthenticatedUser, Depends(require_current_user)]
OptionalUser = Annotated[AuthenticatedUser | None, Depends(get_optional_current_user)]


def login_redirect() -> RedirectResponse:
    return RedirectResponse(url="/login", status_code=303)

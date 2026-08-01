"""Authentication HTTP routes."""

from __future__ import annotations

import logging
import secrets
from datetime import date
from urllib.parse import urlencode

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from constitution_memorizer.auth.exceptions import (
    InvalidCredentialsError,
    RateLimitError,
)
from constitution_memorizer.auth.phone import mask_phone, normalize_e164
from constitution_memorizer.auth.rate_limit import OtpRateLimiter
from constitution_memorizer.auth.sessions import (
    CSRF_COOKIE_NAME,
    SESSION_COOKIE_NAME,
    new_csrf_token,
)

logger = logging.getLogger(__name__)

PUBLIC_PATH_PREFIXES = (
    "/login",
    "/auth/",
    "/static/",
    "/health",
)


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def create_auth_router(templates: Jinja2Templates) -> APIRouter:
    router = APIRouter()

    @router.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @router.get("/login", response_class=HTMLResponse)
    async def login_page(request: Request, error: str | None = None) -> HTMLResponse:
        settings = request.app.state.multiuser_settings
        csrf = request.cookies.get(CSRF_COOKIE_NAME) or new_csrf_token()
        response = templates.TemplateResponse(
            request,
            "login.html",
            {
                "error": error,
                "google_enabled": settings.auth_google_enabled,
                "phone_enabled": settings.auth_phone_enabled,
                "csrf_token": csrf,
                "otp_sent": request.query_params.get("otp") == "1",
                "phone_value": request.query_params.get("phone") or "",
            },
        )
        response.set_cookie(
            CSRF_COOKIE_NAME,
            csrf,
            httponly=False,
            samesite="lax",
            secure=bool(settings.cookie_secure),
            path="/",
        )
        return response

    @router.get("/auth/google/start")
    async def google_start(request: Request) -> RedirectResponse:
        settings = request.app.state.multiuser_settings
        if not settings.auth_google_enabled:
            return RedirectResponse(url="/login?error=google_disabled", status_code=303)
        state = secrets.token_urlsafe(24)
        request.app.state.oauth_states[state] = True
        redirect_url = f"{settings.app_base_url.rstrip('/')}/auth/callback"
        url = request.app.state.auth_provider.get_google_authorization_url(
            redirect_url, state=state
        )
        response = RedirectResponse(url=url, status_code=303)
        response.set_cookie(
            "rtc_oauth_state",
            state,
            httponly=True,
            samesite="lax",
            secure=bool(settings.cookie_secure),
            max_age=600,
            path="/",
        )
        return response

    @router.get("/auth/callback")
    async def auth_callback(request: Request) -> RedirectResponse:
        settings = request.app.state.multiuser_settings
        params = request.query_params
        state = params.get("state") or ""
        cookie_state = request.cookies.get("rtc_oauth_state")
        if not state or state != cookie_state or state not in request.app.state.oauth_states:
            return RedirectResponse(url="/login?error=oauth_state", status_code=303)
        request.app.state.oauth_states.pop(state, None)
        redirect_url = f"{settings.app_base_url.rstrip('/')}/auth/callback"
        try:
            auth_session = request.app.state.auth_provider.exchange_oauth_callback(
                code=params.get("code"),
                access_token=params.get("access_token"),
                refresh_token=params.get("refresh_token"),
                redirect_url=redirect_url,
            )
        except InvalidCredentialsError:
            logger.info("OAuth callback failed")
            return RedirectResponse(url="/login?error=oauth_failed", status_code=303)
        return _establish_session(request, auth_session)

    @router.post("/auth/phone/send")
    async def phone_send(
        request: Request,
        phone: str = Form(...),
        csrf_token: str = Form(...),
    ) -> RedirectResponse:
        settings = request.app.state.multiuser_settings
        if not settings.auth_phone_enabled:
            return RedirectResponse(url="/login?error=phone_disabled", status_code=303)
        if request.cookies.get(CSRF_COOKIE_NAME) != csrf_token:
            return RedirectResponse(url="/login?error=csrf", status_code=303)
        # CAPTCHA integration point — no-op unless enabled.
        if settings.captcha_enabled:
            captcha = (await request.form()).get("captcha_token")
            if not captcha:
                return RedirectResponse(url="/login?error=captcha", status_code=303)
        try:
            normalized = normalize_e164(phone)
        except InvalidCredentialsError:
            return RedirectResponse(url="/login?error=phone_format", status_code=303)
        limiter: OtpRateLimiter = request.app.state.otp_limiter
        ip = _client_ip(request)
        try:
            limiter.check_send(phone=normalized, ip=ip)
            request.app.state.auth_provider.send_phone_otp(normalized)
            limiter.record_send(phone=normalized, ip=ip)
        except RateLimitError:
            logger.info("OTP rate limited for %s", mask_phone(normalized))
        except InvalidCredentialsError:
            logger.info("OTP send failed for %s", mask_phone(normalized))
        # Always generic success — do not reveal account existence.
        qs = urlencode({"otp": "1", "phone": normalized})
        return RedirectResponse(url=f"/login?{qs}", status_code=303)

    @router.post("/auth/phone/verify")
    async def phone_verify(
        request: Request,
        phone: str = Form(...),
        otp: str = Form(...),
        csrf_token: str = Form(...),
    ) -> RedirectResponse:
        settings = request.app.state.multiuser_settings
        if not settings.auth_phone_enabled:
            return RedirectResponse(url="/login?error=phone_disabled", status_code=303)
        if request.cookies.get(CSRF_COOKIE_NAME) != csrf_token:
            return RedirectResponse(url="/login?error=csrf", status_code=303)
        try:
            normalized = normalize_e164(phone)
        except InvalidCredentialsError:
            return RedirectResponse(url="/login?error=phone_format", status_code=303)
        limiter: OtpRateLimiter = request.app.state.otp_limiter
        try:
            limiter.check_verify(phone=normalized)
            auth_session = request.app.state.auth_provider.verify_phone_otp(
                normalized, otp.strip()
            )
            limiter.record_verify_success(phone=normalized)
        except RateLimitError:
            return RedirectResponse(url="/login?error=rate_limited", status_code=303)
        except InvalidCredentialsError:
            limiter.record_verify_failure(phone=normalized)
            qs = urlencode({"otp": "1", "phone": normalized, "error": "bad_otp"})
            return RedirectResponse(url=f"/login?{qs}", status_code=303)
        return _establish_session(request, auth_session)

    @router.post("/logout")
    async def logout(request: Request) -> RedirectResponse:
        settings = request.app.state.multiuser_settings
        session_id = request.cookies.get(SESSION_COOKIE_NAME)
        if session_id:
            request.app.state.session_store.delete(session_id)
        response = RedirectResponse(url="/login", status_code=303)
        response.delete_cookie(SESSION_COOKIE_NAME, path="/")
        response.delete_cookie("rtc_oauth_state", path="/")
        if settings.cookie_secure:
            response.delete_cookie(SESSION_COOKIE_NAME, path="/", secure=True)
        return response

    @router.get("/dashboard", response_class=HTMLResponse)
    async def dashboard(request: Request) -> HTMLResponse:
        user = getattr(request.state, "current_user", None)
        if user is None:
            return RedirectResponse(url="/login", status_code=303)
        eng = request.app.state.engine.for_user(user.id)
        today = date.today()
        due = eng.due_today(as_of=today)
        stats = eng.stats()
        from constitution_memorizer.web.service import continue_unit_id

        cont = continue_unit_id(eng, as_of=today)
        cont_unit = eng.get_unit(cont) if cont else None
        label = user.display_name or (mask_phone(user.phone) if user.phone else user.email or "Learner")
        recent = sorted(
            eng.list_all_progress(),
            key=lambda r: r.updated_at,
            reverse=True,
        )[:5]
        return templates.TemplateResponse(
            request,
            "dashboard.html",
            {
                "user": user,
                "display_label": label,
                "due_count": len(due),
                "started": stats["tracked"],
                "mastered": stats["mastered"],
                "continue_unit": cont_unit,
                "recent": recent,
            },
        )

    return router


def _establish_session(request: Request, auth_session) -> RedirectResponse:
    settings = request.app.state.multiuser_settings
    # Rotate: drop any prior cookie session id by issuing a new one.
    stored = request.app.state.session_store.create(
        auth_session.user,
        access_token=auth_session.access_token,
        refresh_token=auth_session.refresh_token,
    )
    # Application profile upsert (SQLite or Postgres-backed engine repo).
    request.app.state.engine.repo.upsert_profile(
        auth_session.user.id,
        display_name=auth_session.user.display_name,
        avatar_url=auth_session.user.avatar_url,
    )
    response = RedirectResponse(url="/dashboard", status_code=303)
    response.set_cookie(
        SESSION_COOKIE_NAME,
        stored.session_id,
        httponly=True,
        samesite="lax",
        secure=bool(settings.cookie_secure),
        max_age=14 * 24 * 3600,
        path="/",
    )
    response.set_cookie(
        CSRF_COOKIE_NAME,
        stored.csrf_token,
        httponly=False,
        samesite="lax",
        secure=bool(settings.cookie_secure),
        path="/",
    )
    return response


def install_auth_middleware(app) -> None:
    """Redirect unauthenticated users away from protected pages when multiuser is on."""

    @app.middleware("http")
    async def multiuser_auth_gate(request: Request, call_next):
        from constitution_memorizer.web.request_context import bound_engine, bound_memory

        if not getattr(request.app.state, "multiuser_enabled", False):
            request.state.current_user = None
            request.state.bound_engine = request.app.state.engine
            request.state.bound_memory = request.app.state.memory
            token_e = bound_engine.set(request.app.state.engine)
            token_m = bound_memory.set(request.app.state.memory)
            try:
                return await call_next(request)
            finally:
                bound_engine.reset(token_e)
                bound_memory.reset(token_m)

        path = request.url.path
        from constitution_memorizer.auth.dependencies import get_optional_current_user

        user = get_optional_current_user(request)
        request.state.current_user = user
        if user is not None:
            request.state.bound_engine = request.app.state.engine.for_user(user.id)
            request.state.bound_memory = request.app.state.memory.for_user(user.id)
        else:
            request.state.bound_engine = request.app.state.engine
            request.state.bound_memory = request.app.state.memory

        public = path == "/login" or any(
            path.startswith(p) for p in PUBLIC_PATH_PREFIXES if p != "/login"
        )
        if path == "/":
            if user is not None:
                return RedirectResponse(url="/dashboard", status_code=303)
            return RedirectResponse(url="/login", status_code=303)
        if not public and user is None:
            return RedirectResponse(url="/login", status_code=303)

        token_e = bound_engine.set(request.state.bound_engine)
        token_m = bound_memory.set(request.state.bound_memory)
        try:
            return await call_next(request)
        finally:
            bound_engine.reset(token_e)
            bound_memory.reset(token_m)

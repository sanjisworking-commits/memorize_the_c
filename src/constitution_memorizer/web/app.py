"""FastAPI application factory for the learning UI."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from constitution_memorizer.auth.fake_provider import FakeAuthProvider
from constitution_memorizer.auth.rate_limit import OtpRateLimiter
from constitution_memorizer.auth.routes import create_auth_router, install_auth_middleware
from constitution_memorizer.auth.sessions import InMemorySessionStore, PostgresSessionStore
from constitution_memorizer.auth.exceptions import AuthConfigError
from constitution_memorizer.multiuser.settings import MultiUserSettings
from constitution_memorizer.progress.memory import MemoryEngine
from constitution_memorizer.progress.repository import (
    LEARN_MODES,
    VALID_NOTIFICATION_FREQUENCIES,
    VALID_THEMES,
)
from constitution_memorizer.progress.scheduler import ModesIncompleteError, ReminderEngine
from constitution_memorizer.progress.user_ids import LOCAL_USER_ID
from constitution_memorizer.web.request_context import bound_engine, bound_memory
from constitution_memorizer.web.amendments import get_article_amendments, load_amendments
from constitution_memorizer.web.browse import (
    adjacent_article_numbers,
    browse_due_total,
    browse_parts_sections,
    build_article_view,
    list_article_numbers,
    load_reviewed_document,
)
from constitution_memorizer.web.calendar_view import build_calendar_month
from constitution_memorizer.web.gloss import gloss_placeholder_for, load_gloss_placeholders
from constitution_memorizer.web.judicial_evolution import (
    get_judicial_evolution,
    load_judicial_evolution,
)
from constitution_memorizer.web.laws_data import get_law, load_laws
from constitution_memorizer.web.memory_calendar import build_memory_month, schedule_chip_states
from constitution_memorizer.web.progress_stats import progress_dashboard
from constitution_memorizer.web.search import resolve_search
from constitution_memorizer.web.service import (
    LEARN_MODE_LABELS,
    continue_unit_id,
    done_button_state,
    due_checklist,
    earliest_upcoming_revision,
    home_lede,
    kind_badge_label,
    learn_meta_line,
    methods_tracker_line,
    needs_split_choice,
    resolve_learn_target,
    session_progress,
    sibling_chips,
    subclause_stem_text,
    unit_crumb,
    unit_type_label,
)
from constitution_memorizer.web.tables_data import list_table_tabs, load_table_tab, row_is_muted
from constitution_memorizer.web.text_annotations import (
    annotate_plain_text,
    annotations_for_article,
    annotations_for_unit,
    load_text_annotations,
)

WEB_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = WEB_DIR / "templates"
STATIC_DIR = WEB_DIR / "static"
_ALLOWED_PHOTO_SUFFIXES = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".heif"}
_PHOTO_MAGIC: list[tuple[bytes, str, str]] = [
    (b"\x89PNG\r\n\x1a\n", ".png", "image/png"),
    (b"\xff\xd8\xff", ".jpg", "image/jpeg"),
    (b"GIF87a", ".gif", "image/gif"),
    (b"GIF89a", ".gif", "image/gif"),
    (b"RIFF", ".webp", "image/webp"),  # WebP also starts with RIFF….WEBP
]


def _sniff_photo(content: bytes, filename: str) -> tuple[str, str]:
    """Return (suffix, media_type) from magic bytes, else filename suffix."""
    for magic, suffix, media_type in _PHOTO_MAGIC:
        if content.startswith(magic):
            if suffix == ".webp" and b"WEBP" not in content[:16]:
                continue
            return suffix, media_type
    # HEIC/HEIF brands in ISO BMFF
    if len(content) >= 12 and content[4:8] == b"ftyp":
        brand = content[8:12]
        if brand in {b"heic", b"heif", b"mif1", b"msf1", b"hevc"}:
            return ".heic", "image/heic"
    suffix = Path(filename).suffix.lower() or ".jpg"
    if suffix not in _ALLOWED_PHOTO_SUFFIXES:
        suffix = ".jpg"
    media_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".heic": "image/heic",
        ".heif": "image/heif",
    }
    return suffix, media_types.get(suffix, "application/octet-stream")


def create_app(
    *,
    units_path: Path | str | None = None,
    db_path: Path | str | None = None,
    reviewed_path: Path | str | None = None,
    amendments_path: Path | str | None = None,
    gloss_placeholders_path: Path | str | None = None,
    text_annotations_path: Path | str | None = None,
    judicial_evolution_path: Path | str | None = None,
    multiuser: bool = False,
    multiuser_settings: MultiUserSettings | None = None,
    auth_provider=None,
    session_store=None,
) -> FastAPI:
    """Create the learning UI app bound to concrete unit/progress paths."""
    root = Path.cwd()
    resolved_units = Path(units_path or root / "data" / "output" / "learning_units.json")
    resolved_db = Path(db_path or root / "data" / "progress" / "progress.db")
    resolved_reviewed = Path(
        reviewed_path
        if reviewed_path is not None
        else root / "data" / "output" / "constitution.reviewed.json"
    )
    resolved_amendments = Path(
        amendments_path
        if amendments_path is not None
        else root / "data" / "reference" / "amendments.seed.json"
    )
    resolved_gloss_placeholders = Path(
        gloss_placeholders_path
        if gloss_placeholders_path is not None
        else root / "data" / "reference" / "gloss_placeholders.seed.json"
    )
    resolved_text_annotations = Path(
        text_annotations_path
        if text_annotations_path is not None
        else root / "data" / "reference" / "text_annotations.json"
    )
    resolved_judicial_evolution = Path(
        judicial_evolution_path
        if judicial_evolution_path is not None
        else root / "data" / "reference" / "judicial_evolution.seed.json"
    )

    if not resolved_units.exists():
        raise FileNotFoundError(
            f"learning_units.json not found at {resolved_units}. "
            "Run: python -m constitution_memorizer.cli generate-units --force"
        )

    settings = multiuser_settings or MultiUserSettings()
    # Opt-in only via the multiuser= argument (CLI sets this from MULTIUSER_ENABLED).
    # Do not infer from process env here — that leaks across pytest cases.
    multiuser_on = bool(multiuser)
    # Real Supabase credentials are required only when multi-user is on and
    # the caller did not inject a test/fake auth provider.
    if multiuser_on and auth_provider is None:
        settings.validate_for_startup(require_secrets=True)
        missing = settings.missing_supabase()
        if missing:
            raise AuthConfigError(
                "Missing "
                + ", ".join(missing)
                + ". Add them to .env in the repo root, then restart. "
                "SUPABASE_URL must be https://<project-ref>.supabase.co "
                "(not https://supabase.com/dashboard/...)."
            )

    resolved_db = Path(resolved_db).expanduser().resolve()
    resolved_units = Path(resolved_units).expanduser().resolve()
    engine = ReminderEngine.from_paths(
        resolved_db, resolved_units, user_id=LOCAL_USER_ID
    )
    memory = MemoryEngine(
        engine.repo.conn,
        resolved_db.parent / "memory_media",
        user_id=LOCAL_USER_ID,
    )
    reviewed = load_reviewed_document(
        resolved_reviewed if resolved_reviewed.exists() else None
    )
    # Stale non-editable installs often miss Browse Part segregation — surface paths.
    import constitution_memorizer.web.browse as _browse_mod  # noqa: PLC0415

    print(
        f"Browse module: {_browse_mod.__file__} "
        f"(reviewed={'yes' if reviewed is not None else 'missing → Part seed/tags'})"
    )
    amendments = load_amendments(
        resolved_amendments if resolved_amendments.exists() else None
    )
    gloss_placeholders = load_gloss_placeholders(
        resolved_gloss_placeholders if resolved_gloss_placeholders.exists() else None
    )
    text_annotations = load_text_annotations(
        resolved_text_annotations if resolved_text_annotations.exists() else None
    )
    judicial_evolution = load_judicial_evolution(
        resolved_judicial_evolution if resolved_judicial_evolution.exists() else None
    )

    def _theme_for_request(request: Request) -> str:
        if getattr(request.state, "is_guest", False) and app.state.multiuser_enabled:
            return "auto"
        bound = getattr(request.state, "bound_engine", None) or app.state.engine
        return bound.get_theme()

    def _due_for_request(request: Request) -> int:
        if getattr(request.state, "is_guest", False) or getattr(
            request.state, "current_user", None
        ) is None:
            if app.state.multiuser_enabled:
                return 0
        bound = getattr(request.state, "bound_engine", None) or app.state.engine
        return browse_due_total(bound)

    templates = Jinja2Templates(
        directory=str(TEMPLATES_DIR),
        context_processors=[
            lambda request: {
                "app_name": "Recall the C",
                "theme_preference": _theme_for_request(request),
                "browse_due_total": _due_for_request(request),
                "current_user": getattr(request.state, "current_user", None),
                "is_guest": bool(
                    app.state.multiuser_enabled
                    and getattr(request.state, "current_user", None) is None
                ),
                "multiuser_enabled": app.state.multiuser_enabled,
                "csrf_token": (
                    getattr(getattr(request.state, "auth_session", None), "csrf_token", None)
                    or request.cookies.get("rtc_csrf")
                ),
            }
        ],
    )

    app = FastAPI(title="Recall the C", version="0.8.0")
    app.state.engine = engine
    app.state.memory = memory
    app.state.reviewed = reviewed
    app.state.amendments = amendments
    app.state.gloss_placeholders = gloss_placeholders
    app.state.text_annotations = text_annotations
    app.state.judicial_evolution = judicial_evolution
    app.state.units_path = resolved_units
    app.state.db_path = resolved_db
    app.state.reviewed_path = resolved_reviewed
    app.state.multiuser_enabled = multiuser_on
    app.state.multiuser_settings = settings
    app.state.oauth_states = {}
    app.state.otp_limiter = OtpRateLimiter()
    if auth_provider is not None:
        app.state.auth_provider = auth_provider
    elif multiuser_on:
        from constitution_memorizer.auth.supabase_provider import SupabaseAuthProvider

        app.state.auth_provider = SupabaseAuthProvider(
            supabase_url=settings.supabase_url.strip(),
            anon_key=settings.supabase_anon_key.strip(),
        )
    else:
        app.state.auth_provider = FakeAuthProvider()
    if session_store is not None:
        app.state.session_store = session_store
    elif multiuser_on and settings.database_url.startswith("postgresql"):
        app.state.session_store = PostgresSessionStore(settings.database_url)
    else:
        app.state.session_store = InMemorySessionStore()

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    install_auth_middleware(app)
    app.include_router(create_auth_router(templates))

    def _engine() -> ReminderEngine:
        bound = bound_engine.get()
        if bound is not None:
            return bound
        return app.state.engine

    def _memory() -> MemoryEngine:
        bound = bound_memory.get()
        if bound is not None:
            return bound
        return app.state.memory

    def _modes_payload(unit_id: str, seen: set[str] | None = None) -> dict[str, object]:
        current = seen if seen is not None else _engine().modes_seen(unit_id)
        return {
            "seen": sorted(current),
            "count": len(current),
            "remaining": max(0, 6 - len(current)),
            "complete": len(current) >= 6,
            "tracker": methods_tracker_line(len(current)),
        }
    @app.get("/", response_class=HTMLResponse)
    async def home(request: Request) -> HTMLResponse:
        if app.state.multiuser_enabled and getattr(request.state, "current_user", None) is None:
            return templates.TemplateResponse(
                request,
                "guest_home.html",
                {},
            )
        eng = _engine()
        today = date.today()
        due = due_checklist(eng, as_of=today)
        cont = continue_unit_id(eng, as_of=today)
        cont_unit = eng.get_unit(cont) if cont else None
        stats = eng.stats()
        upcoming = earliest_upcoming_revision(eng, as_of=today)
        all_caught_up = not due and cont_unit is None
        caught_up_detail = "Nothing due today."
        if all_caught_up and upcoming is not None:
            caught_up_detail = (
                f"Nothing due today. Next review lands "
                f"{upcoming.day} {upcoming.strftime('%b')}."
            )
        elif all_caught_up:
            caught_up_detail = "Nothing due today. Start from Browse when you are ready."

        continue_meta = None
        if cont_unit is not None:
            bits = [
                unit_type_label(cont_unit),
                f"~{cont_unit.estimated_learning_time}s",
                f"difficulty {cont_unit.difficulty}/5",
            ]
            continue_meta = " · ".join(bits)

        return templates.TemplateResponse(
            request,
            "home.html",
            {
                "due_units": due,
                "continue_unit": cont_unit,
                "continue_kind": (
                    unit_type_label(cont_unit) if cont_unit is not None else None
                ),
                "continue_meta": continue_meta,
                "stats": stats,
                "today": today,
                "today_label": (
                    f"{today.strftime('%A')}, {today.day} {today.strftime('%B %Y')}"
                ),
                "home_lede": home_lede(
                    due_count=len(due),
                    has_continue=cont_unit is not None,
                ),
                "all_caught_up": all_caught_up,
                "caught_up_detail": caught_up_detail,
                "stat_line": (
                    f"{stats['review']} in review · "
                    f"{stats['mastered']} mastered · "
                    f"{stats['split_preferences']} split choices"
                ),
                "unit_type_label": unit_type_label,
            },
        )

    @app.get("/learn", response_class=HTMLResponse)
    async def learn_index(request: Request) -> RedirectResponse:
        eng = _engine()
        today = date.today()
        is_guest = bool(
            app.state.multiuser_enabled
            and getattr(request.state, "current_user", None) is None
        )
        if not is_guest:
            due = eng.due_today(as_of=today)
            if due:
                return RedirectResponse(
                    url=f"/learn/{due[0].learning_unit_id}", status_code=303
                )
            cont = continue_unit_id(eng, as_of=today)
            if cont:
                return RedirectResponse(url=f"/learn/{cont}", status_code=303)
        return RedirectResponse(url="/browse", status_code=303)

    @app.get("/learn/{unit_id}", response_class=HTMLResponse)
    async def learn(
        request: Request,
        unit_id: str,
        mode: str = "read",
    ) -> HTMLResponse:
        eng = _engine()
        unit = eng.get_unit(unit_id)
        if unit is None:
            raise HTTPException(status_code=404, detail="Learning unit not found")

        learn_mode = mode if mode in {"read", "cloze", "letters", "type", "recite", "card"} else "read"
        is_guest_early = bool(
            app.state.multiuser_enabled
            and getattr(request.state, "current_user", None) is None
        )

        # Guests skip split preference (no personal data); show the clause as-is.
        if not is_guest_early and needs_split_choice(eng, unit):
            return RedirectResponse(
                url=f"/learn/{unit_id}/choose",
                status_code=303,
            )

        target_id = unit_id if is_guest_early else resolve_learn_target(eng, unit_id)
        if target_id != unit_id:
            suffix = f"?mode={learn_mode}" if learn_mode != "read" else ""
            return RedirectResponse(
                url=f"/learn/{target_id}{suffix}",
                status_code=303,
            )

        target = eng.get_unit(target_id)
        if target is None:
            raise HTTPException(status_code=404, detail="Learning unit not found")

        is_guest = bool(
            app.state.multiuser_enabled
            and getattr(request.state, "current_user", None) is None
        )
        # Guests may try modes without writing progress.
        if is_guest:
            seen: set[str] = {learn_mode}
            progress = None
            done_count, chain_len = 0, 1
            pct = 0
            # Guests can click Done/Again to open the sign-in prompt.
            done_unlocked = True
            done_label = "Mark as mastered"
        else:
            seen = eng.mark_mode_seen(target.id, learn_mode)
            progress = eng.get_progress(target.id)
            done_count, _position, chain_len = session_progress(eng, target)
            pct = int(round(100 * done_count / chain_len)) if chain_len else 0
            done_state = done_button_state(target, seen)
            done_unlocked = done_state["unlocked"]
            done_label = done_state["label"]
        modes_payload = _modes_payload(target.id, seen)

        chips = sibling_chips(eng, target)
        stem = subclause_stem_text(eng, target)
        rail_kind = (
            "letters"
            if target.type.value == "SUBCLAUSE"
            else ("clauses" if chips else None)
        )
        curated = get_article_amendments(app.state.amendments, target.article_number)
        amend_note = curated.learn_note if curated is not None else None
        catalog = app.state.text_annotations
        unit_anns = annotations_for_unit(catalog, target.id)
        notes = catalog.notes if hasattr(catalog, "notes") else {}
        annotated_text = annotate_plain_text(
            target.text,
            unit_anns,
            notes=notes,
            unit_id=target.id,
        )
        return templates.TemplateResponse(
            request,
            "learn.html",
            {
                "unit": target,
                "progress": progress,
                "kind_badge": kind_badge_label(target),
                "unit_crumb": unit_crumb(target),
                "session_label": f"{done_count} of {chain_len}",
                "session_pct": pct,
                "sibling_chips": chips,
                "rail_kind": rail_kind,
                "stem_text": stem,
                "learn_meta": learn_meta_line(target, progress) if progress else "Guest try",
                "done_label": done_label,
                "done_unlocked": done_unlocked,
                "modes_seen": seen,
                "modes_tracker": modes_payload["tracker"],
                "mode_labels": LEARN_MODE_LABELS,
                "learn_modes": LEARN_MODES,
                "learn_mode": learn_mode,
                "amend_note": amend_note,
                "annotated_text": annotated_text,
                "has_text_annotations": bool(unit_anns),
                "is_guest": is_guest,
                "read_hint": (
                    "Bare Act wording, verbatim. Read it twice, then pick a recall mode."
                ),
            },
        )

    @app.post("/learn/{unit_id}/seen")
    async def learn_mode_seen(
        unit_id: str,
        mode: str = Form(...),
    ) -> JSONResponse:
        eng = _engine()
        if eng.get_unit(unit_id) is None:
            raise HTTPException(status_code=404, detail="Learning unit not found")
        if mode not in LEARN_MODES:
            raise HTTPException(status_code=400, detail="Invalid learn mode")
        seen = eng.mark_mode_seen(unit_id, mode)
        unit = eng.get_unit(unit_id)
        assert unit is not None
        payload = _modes_payload(unit_id, seen)
        payload["done"] = done_button_state(unit, seen)
        return JSONResponse(payload)

    @app.post("/learn/{unit_id}/done")
    async def learn_done(unit_id: str) -> RedirectResponse:
        eng = _engine()
        if eng.get_unit(unit_id) is None:
            raise HTTPException(status_code=404, detail="Learning unit not found")
        try:
            result = eng.mark_done(unit_id, as_of=date.today())
        except ModesIncompleteError:
            return RedirectResponse(url=f"/learn/{unit_id}", status_code=303)
        return _redirect_after_learn(eng, result.next_unit_id)

    @app.post("/learn/{unit_id}/again")
    async def learn_again(unit_id: str) -> RedirectResponse:
        """Defer this unit until tomorrow, then advance to the next unit."""
        eng = _engine()
        if eng.get_unit(unit_id) is None:
            raise HTTPException(status_code=404, detail="Learning unit not found")
        result = eng.defer_until_tomorrow(unit_id, as_of=date.today())
        return _redirect_after_learn(eng, result.next_unit_id)

    def _redirect_after_learn(
        eng: ReminderEngine,
        next_unit_id: str | None,
    ) -> RedirectResponse:
        if next_unit_id and eng.get_unit(next_unit_id):
            nxt = eng.get_unit(next_unit_id)
            assert nxt is not None
            if needs_split_choice(eng, nxt):
                return RedirectResponse(
                    url=f"/learn/{next_unit_id}/choose",
                    status_code=303,
                )
            return RedirectResponse(url=f"/learn/{next_unit_id}", status_code=303)
        return RedirectResponse(url="/", status_code=303)

    @app.get("/learn/{clause_id}/choose", response_class=HTMLResponse)
    async def choose_get(request: Request, clause_id: str) -> HTMLResponse:
        eng = _engine()
        unit = eng.get_unit(clause_id)
        if unit is None:
            raise HTTPException(status_code=404, detail="Learning unit not found")
        if not unit.allows_letter_split:
            return RedirectResponse(url=f"/learn/{clause_id}", status_code=303)
        existing = eng.get_split_preference(clause_id)
        if existing is not None:
            target = eng.next_to_learn_from_clause(clause_id) or clause_id
            return RedirectResponse(url=f"/learn/{target}", status_code=303)
        return templates.TemplateResponse(
            request,
            "choose.html",
            {"unit": unit},
        )

    @app.post("/learn/{clause_id}/choose")
    async def choose_post(
        clause_id: str,
        mode: str = Form(...),
    ) -> RedirectResponse:
        eng = _engine()
        unit = eng.get_unit(clause_id)
        if unit is None:
            raise HTTPException(status_code=404, detail="Learning unit not found")
        if not unit.allows_letter_split:
            return RedirectResponse(url=f"/learn/{clause_id}", status_code=303)
        if mode not in ("whole", "letters"):
            raise HTTPException(status_code=400, detail="mode must be whole or letters")
        eng.set_split_preference(clause_id, mode)  # type: ignore[arg-type]
        target = eng.next_to_learn_from_clause(clause_id) or clause_id
        return RedirectResponse(url=f"/learn/{target}", status_code=303)

    @app.post("/learn/{unit_id}/reset")
    async def reset_unit(
        unit_id: str,
        mode: str = Query(default="read"),
    ) -> RedirectResponse:
        eng = _engine()
        if eng.get_unit(unit_id) is None:
            raise HTTPException(status_code=404, detail="Learning unit not found")
        eng.delete_progress(unit_id)
        eng.clear_modes_seen(unit_id)
        learn_mode = mode if mode in LEARN_MODES else "read"
        # Re-seed the currently open mode on the next GET; redirect preserves mode.
        suffix = f"?mode={learn_mode}" if learn_mode != "read" else ""
        return RedirectResponse(url=f"/learn/{unit_id}{suffix}", status_code=303)

    @app.post("/reset")
    async def reset_all() -> RedirectResponse:
        """Clear this user's progress and preferences (study reset)."""
        eng = _engine()
        eng.reset_all_personal_data()
        return RedirectResponse(url="/", status_code=303)

    @app.get("/browse", response_class=HTMLResponse)
    async def browse_index(request: Request) -> HTMLResponse:
        eng = _engine()
        sections = browse_parts_sections(eng, app.state.reviewed)
        parts_source = "reviewed" if app.state.reviewed is not None else "units-seed"
        return templates.TemplateResponse(
            request,
            "browse_index.html",
            {
                "sections": sections,
                "has_reviewed": app.state.reviewed is not None,
                "parts_source": parts_source,
            },
        )

    @app.get("/browse/article/{article_number}", response_class=HTMLResponse)
    async def browse_article(request: Request, article_number: str) -> HTMLResponse:
        eng = _engine()
        view = build_article_view(
            eng,
            app.state.reviewed,
            article_number,
            amendments_catalog=app.state.amendments,
        )
        if view is None:
            raise HTTPException(status_code=404, detail="Article not found")
        prev_number, next_number = adjacent_article_numbers(
            eng, app.state.reviewed, view.article_number
        )
        gloss_text = eng.get_gloss(view.article_number) or ""
        gloss_ph = gloss_placeholder_for(
            app.state.gloss_placeholders, view.article_number
        )
        judicial = get_judicial_evolution(
            app.state.judicial_evolution, view.article_number
        )
        catalog = app.state.text_annotations
        browse_anns = annotations_for_article(
            catalog,
            view.article_number,
            [u.id for u in view.learn_units],
        )
        notes = catalog.notes if hasattr(catalog, "notes") else {}
        annotated_text = annotate_plain_text(
            view.full_text,
            browse_anns,
            notes=notes,
            unit_id=f"browse-article-{view.article_number}",
        )
        return templates.TemplateResponse(
            request,
            "browse_article.html",
            {
                "article": view,
                "prev_article": prev_number,
                "next_article": next_number,
                "gloss_text": gloss_text,
                "gloss_placeholder": gloss_ph,
                "judicial_evolution": judicial,
                "annotated_text": annotated_text,
                "has_text_annotations": bool(browse_anns),
            },
        )

    @app.put("/browse/article/{article_number}/gloss")
    async def put_article_gloss(article_number: str, request: Request) -> JSONResponse:
        eng = _engine()
        numbers = {n.lower() for n in list_article_numbers(eng, app.state.reviewed)}
        if article_number.lower() not in numbers:
            # Allow gloss for units-known articles even if not in reviewed list
            has_units = any(
                (u.article_number or "").lower() == article_number.lower()
                for u in eng.units.values()
            )
            if not has_units:
                raise HTTPException(status_code=404, detail="Article not found")
        try:
            payload = await request.json()
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail="Invalid JSON") from exc
        text = str(payload.get("text", "")) if isinstance(payload, dict) else ""
        trimmed = text.strip()
        if not trimmed:
            eng.delete_gloss(article_number)
            return JSONResponse({"ok": True, "text": "", "words": 0})
        eng.upsert_gloss(article_number, text)
        words = len(trimmed.split())
        return JSONResponse({"ok": True, "text": text, "words": words})

    @app.delete("/browse/article/{article_number}/gloss")
    async def delete_article_gloss(article_number: str) -> JSONResponse:
        eng = _engine()
        eng.delete_gloss(article_number)
        return JSONResponse({"ok": True, "text": "", "words": 0})

    @app.get("/search", response_class=HTMLResponse)
    async def search_page(
        request: Request,
        q: str | None = Query(default=None),
    ) -> HTMLResponse:
        eng = _engine()
        hit = None
        if q and q.strip():
            hit = resolve_search(eng, q.strip())
            if hit.redirect_url:
                return RedirectResponse(url=hit.redirect_url, status_code=303)
        return templates.TemplateResponse(
            request,
            "search.html",
            {
                "q": q or "",
                "hit": hit,
            },
        )

    @app.get("/calendar", response_class=HTMLResponse)
    async def calendar_page(
        request: Request,
        year: int | None = Query(default=None),
        month: int | None = Query(default=None),
    ) -> HTMLResponse:
        today = date.today()
        y = year if year is not None else today.year
        m = month if month is not None else today.month
        if m < 1 or m > 12 or y < 1 or y > 9999:
            raise HTTPException(status_code=400, detail="Invalid year or month")
        view = build_calendar_month(_engine(), year=y, month=m, today=today)
        return templates.TemplateResponse(
            request,
            "calendar.html",
            {"calendar": view},
        )

    @app.get("/progress", response_class=HTMLResponse)
    async def progress_page(request: Request) -> HTMLResponse:
        if app.state.multiuser_enabled and getattr(request.state, "current_user", None) is None:
            return templates.TemplateResponse(
                request,
                "guest_gate.html",
                {"gate_kind": "progress", "reason": "default"},
            )
        dashboard = progress_dashboard(
            _engine(),
            reviewed=app.state.reviewed,
            today=date.today(),
        )
        return templates.TemplateResponse(
            request,
            "progress.html",
            {"dashboard": dashboard},
        )

    @app.get("/tables", response_class=HTMLResponse)
    async def tables_page(
        request: Request,
        tab: str | None = Query(default=None),
    ) -> HTMLResponse:
        tabs = list_table_tabs()
        if not tabs:
            raise HTTPException(
                status_code=500,
                detail="Tables data missing — run from repo root and pull sprint-29",
            )
        tab_ids = {t.id for t in tabs}
        selected = tab if tab in tab_ids else tabs[0].id
        payload = load_table_tab(selected)
        if payload is None:
            raise HTTPException(status_code=404, detail=f"Table not found: {selected}")
        return templates.TemplateResponse(
            request,
            "tables.html",
            {
                "tabs": tabs,
                "selected": selected,
                "payload": payload,
                "row_is_muted": row_is_muted,
            },
        )

    @app.get("/laws", response_class=HTMLResponse)
    async def laws_page(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(
            request,
            "laws.html",
            {"acts": load_laws()},
        )

    @app.get("/laws/{law_id}", response_class=HTMLResponse)
    async def law_detail_page(request: Request, law_id: str) -> HTMLResponse:
        act = get_law(law_id)
        if act is None:
            raise HTTPException(status_code=404, detail="Law not found")
        tracked = set(list_article_numbers(_engine(), app.state.reviewed))
        return templates.TemplateResponse(
            request,
            "law_detail.html",
            {"act": act, "tracked_articles": tracked},
        )

    @app.get("/memory", response_class=HTMLResponse)
    async def memory_page(
        request: Request,
        year: int | None = Query(default=None),
        month: int | None = Query(default=None),
    ) -> HTMLResponse:
        today = date.today()
        y = year if year is not None else today.year
        m = month if month is not None else today.month
        if m < 1 or m > 12:
            raise HTTPException(status_code=400, detail="Invalid month")
        try:
            calendar = build_memory_month(_memory(), year=y, month=m, today=today)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        entries = _memory().list_all()
        photo_ids = {
            entry.id for entry in entries if _memory().photo_file(entry.id) is not None
        }
        return templates.TemplateResponse(
            request,
            "memory.html",
            {
                "calendar": calendar,
                "entries": entries,
                "photo_ids": photo_ids,
            },
        )

    @app.post("/memory")
    async def memory_create(
        title: str = Form(...),
        acronym: str = Form(""),
    ) -> RedirectResponse:
        cleaned = title.strip()
        if not cleaned:
            raise HTTPException(status_code=400, detail="Title required")
        entry = _memory().create(title=cleaned, acronym=acronym.strip())
        return RedirectResponse(url=f"/memory/{entry.id}", status_code=303)

    @app.get("/memory/media/{entry_id}")
    async def memory_media(entry_id: str) -> FileResponse:
        path = _memory().photo_file(entry_id)
        if path is None:
            raise HTTPException(status_code=404, detail="Photo not found")
        _, media_type = _sniff_photo(path.read_bytes()[:64], path.name)
        return FileResponse(path, media_type=media_type)

    @app.get("/memory/{entry_id}", response_class=HTMLResponse)
    async def memory_detail_page(request: Request, entry_id: str) -> HTMLResponse:
        entry = _memory().get(entry_id)
        if entry is None:
            raise HTTPException(status_code=404, detail="Memory entry not found")
        photo_path = _memory().photo_file(entry_id)
        return templates.TemplateResponse(
            request,
            "memory_detail.html",
            {
                "entry": entry,
                "schedule": schedule_chip_states(entry, today=date.today()),
                "has_photo": photo_path is not None,
            },
        )

    @app.post("/memory/{entry_id}/notes")
    async def memory_save_notes(
        entry_id: str,
        notes: str = Form(""),
    ) -> RedirectResponse:
        if _memory().get(entry_id) is None:
            raise HTTPException(status_code=404, detail="Memory entry not found")
        _memory().update_notes(entry_id, notes)
        return RedirectResponse(url=f"/memory/{entry_id}", status_code=303)

    @app.post("/memory/{entry_id}/done")
    async def memory_done(entry_id: str) -> RedirectResponse:
        if _memory().get(entry_id) is None:
            raise HTTPException(status_code=404, detail="Memory entry not found")
        _memory().mark_done(entry_id)
        return RedirectResponse(url=f"/memory/{entry_id}", status_code=303)

    @app.post("/memory/{entry_id}/photo")
    async def memory_upload_photo(
        entry_id: str,
        photo: UploadFile = File(...),
    ) -> RedirectResponse:
        mem = _memory()
        if mem.get(entry_id) is None:
            raise HTTPException(status_code=404, detail="Memory entry not found")
        content = await photo.read()
        if not content:
            raise HTTPException(status_code=400, detail="Empty upload")
        filename = photo.filename or "note.jpg"
        suffix, _media_type = _sniff_photo(content, filename)
        if suffix not in _ALLOWED_PHOTO_SUFFIXES:
            raise HTTPException(status_code=400, detail="Unsupported image type")
        user_dir = mem.user_media_dir()
        # Remove any prior file for this entry (extension may change after sniff).
        for old in user_dir.glob(f"{entry_id}.*"):
            try:
                old.unlink()
            except OSError:
                pass
        dest_name = f"{entry_id}{suffix}"
        dest = user_dir / dest_name
        dest.write_bytes(content)
        from constitution_memorizer.progress.user_ids import as_user_id

        storage_key = f"{as_user_id(mem.user_id)}/{dest_name}"
        mem.set_photo(entry_id, storage_key)
        return RedirectResponse(url=f"/memory/{entry_id}", status_code=303)

    @app.get("/settings", response_class=HTMLResponse)
    async def settings_page(
        request: Request,
        saved: int | None = Query(default=None),
    ) -> HTMLResponse:
        eng = _engine()
        return templates.TemplateResponse(
            request,
            "settings.html",
            {
                "frequency": eng.get_notification_frequency(),
                "news_articles": eng.get_news_articles_raw(),
                "saved": bool(saved),
            },
        )

    @app.post("/settings")
    async def settings_save(
        notification_frequency: str = Form(...),
        news_articles: str = Form(""),
    ) -> RedirectResponse:
        if notification_frequency not in VALID_NOTIFICATION_FREQUENCIES:
            raise HTTPException(status_code=400, detail="Invalid notification frequency")
        eng = _engine()
        eng.set_notification_frequency(notification_frequency)  # type: ignore[arg-type]
        eng.set_news_articles_raw(news_articles)
        return RedirectResponse(url="/settings?saved=1", status_code=303)

    @app.post("/api/theme")
    async def theme_save(theme: str = Form(...)) -> JSONResponse:
        if theme not in VALID_THEMES:
            raise HTTPException(status_code=400, detail="Invalid theme")
        _engine().set_theme(theme)  # type: ignore[arg-type]
        return JSONResponse({"theme": theme})

    return app

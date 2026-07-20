"""FastAPI application factory for the learning UI."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from constitution_memorizer.progress.scheduler import ReminderEngine
from constitution_memorizer.web.browse import (
    adjacent_article_numbers,
    build_article_view,
    list_article_numbers,
    load_reviewed_document,
)
from constitution_memorizer.web.progress_stats import progress_dashboard
from constitution_memorizer.web.search import resolve_search
from constitution_memorizer.web.service import (
    continue_unit_id,
    done_button_label,
    due_checklist,
    earliest_upcoming_revision,
    home_lede,
    kind_badge_label,
    learn_meta_line,
    needs_split_choice,
    resolve_learn_target,
    session_progress,
    sibling_chips,
    subclause_stem_text,
    unit_crumb,
    unit_type_label,
)

WEB_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = WEB_DIR / "templates"
STATIC_DIR = WEB_DIR / "static"


def create_app(
    *,
    units_path: Path | str | None = None,
    db_path: Path | str | None = None,
    reviewed_path: Path | str | None = None,
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

    if not resolved_units.exists():
        raise FileNotFoundError(
            f"learning_units.json not found at {resolved_units}. "
            "Run: python -m constitution_memorizer.cli generate-units --force"
        )

    engine = ReminderEngine.from_paths(resolved_db, resolved_units)
    reviewed = load_reviewed_document(
        resolved_reviewed if resolved_reviewed.exists() else None
    )
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

    app = FastAPI(title="Constitution Memorizer", version="0.5.0")
    app.state.engine = engine
    app.state.reviewed = reviewed
    app.state.units_path = resolved_units
    app.state.db_path = resolved_db
    app.state.reviewed_path = resolved_reviewed
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    def _engine() -> ReminderEngine:
        return app.state.engine

    @app.get("/", response_class=HTMLResponse)
    async def home(request: Request) -> HTMLResponse:
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

        learn_mode = mode if mode in {"read", "cloze", "letters", "type", "card"} else "read"

        if needs_split_choice(eng, unit):
            return RedirectResponse(
                url=f"/learn/{unit_id}/choose",
                status_code=303,
            )

        target_id = resolve_learn_target(eng, unit_id)
        if target_id != unit_id:
            suffix = f"?mode={learn_mode}" if learn_mode != "read" else ""
            return RedirectResponse(
                url=f"/learn/{target_id}{suffix}",
                status_code=303,
            )

        target = eng.get_unit(target_id)
        if target is None:
            raise HTTPException(status_code=404, detail="Learning unit not found")

        progress = eng.repo.get_progress(target.id)
        done_count, _position, chain_len = session_progress(eng, target)
        pct = int(round(100 * done_count / chain_len)) if chain_len else 0
        chips = sibling_chips(eng, target)
        stem = subclause_stem_text(eng, target)
        rail_kind = (
            "letters"
            if target.type.value == "SUBCLAUSE"
            else ("clauses" if chips else None)
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
                "learn_meta": learn_meta_line(target, progress),
                "done_label": done_button_label(target),
                "learn_mode": learn_mode,
                "read_hint": (
                    "Bare Act wording, verbatim. Read it twice, then pick a recall mode."
                ),
            },
        )

    @app.post("/learn/{unit_id}/done")
    async def learn_done(unit_id: str) -> RedirectResponse:
        eng = _engine()
        if eng.get_unit(unit_id) is None:
            raise HTTPException(status_code=404, detail="Learning unit not found")
        result = eng.mark_done(unit_id, as_of=date.today())
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
    async def reset_unit(unit_id: str) -> RedirectResponse:
        eng = _engine()
        if eng.get_unit(unit_id) is None:
            raise HTTPException(status_code=404, detail="Learning unit not found")
        eng.repo.conn.execute(
            "DELETE FROM learning_unit_progress WHERE learning_unit_id = ?",
            (unit_id,),
        )
        eng.repo.conn.commit()
        return RedirectResponse(url=f"/learn/{unit_id}", status_code=303)

    @app.post("/reset")
    async def reset_all() -> RedirectResponse:
        """Clear all progress and preferences (study reset)."""
        eng = _engine()
        eng.repo.conn.execute("DELETE FROM learning_unit_progress")
        eng.repo.conn.execute("DELETE FROM split_preference")
        eng.repo.conn.commit()
        return RedirectResponse(url="/", status_code=303)

    @app.get("/browse", response_class=HTMLResponse)
    async def browse_index(request: Request) -> HTMLResponse:
        eng = _engine()
        numbers = list_article_numbers(eng, app.state.reviewed)
        return templates.TemplateResponse(
            request,
            "browse_index.html",
            {
                "article_numbers": numbers,
                "has_reviewed": app.state.reviewed is not None,
            },
        )

    @app.get("/browse/article/{article_number}", response_class=HTMLResponse)
    async def browse_article(request: Request, article_number: str) -> HTMLResponse:
        eng = _engine()
        view = build_article_view(eng, app.state.reviewed, article_number)
        if view is None:
            raise HTTPException(status_code=404, detail="Article not found")
        prev_number, next_number = adjacent_article_numbers(
            eng, app.state.reviewed, view.article_number
        )
        return templates.TemplateResponse(
            request,
            "browse_article.html",
            {
                "article": view,
                "prev_article": prev_number,
                "next_article": next_number,
            },
        )

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
    async def calendar_stub(request: Request) -> HTMLResponse:
        """Sheet nav target; full month grid arrives in Sprint 18."""
        return templates.TemplateResponse(
            request,
            "calendar.html",
            {},
        )

    @app.get("/progress", response_class=HTMLResponse)
    async def progress_page(request: Request) -> HTMLResponse:
        dashboard = progress_dashboard(_engine())
        # Show articles with any progress first, then a short head of the rest.
        started = [a for a in dashboard["articles"] if a.completed > 0]
        rest = [a for a in dashboard["articles"] if a.completed == 0][:40]
        return templates.TemplateResponse(
            request,
            "progress.html",
            {
                "dashboard": dashboard,
                "started_articles": started,
                "sample_articles": rest,
            },
        )

    return app

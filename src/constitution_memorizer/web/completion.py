"""Completion affirmation context for Learn Done (validated ``?done=``)."""

from __future__ import annotations

from datetime import date
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from fastapi import Request

from constitution_memorizer.learning.schemas import LearningUnit
from constitution_memorizer.progress.scheduler import ReminderEngine
from constitution_memorizer.progress.user_ids import LOCAL_USER_ID
from constitution_memorizer.web.quotes import get_quote_for
from constitution_memorizer.web.service import needs_split_choice


def wants_json(request: Request) -> bool:
    accept = (request.headers.get("accept") or "").lower()
    requested = (request.headers.get("x-requested-with") or "").lower()
    return "application/json" in accept or requested == "xmlhttprequest"


def strip_done_param(url: str) -> str:
    parts = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k != "done"]
    return urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment)
    )


def next_learn_url(
    eng: ReminderEngine,
    next_unit_id: str | None,
    *,
    done_unit_id: str | None = None,
    multiuser: bool = False,
) -> str:
    suffix = f"?done={done_unit_id}" if done_unit_id else ""
    if next_unit_id and eng.get_unit(next_unit_id):
        nxt = eng.get_unit(next_unit_id)
        assert nxt is not None
        if needs_split_choice(eng, nxt):
            return f"/learn/{next_unit_id}/choose{suffix}"
        return f"/learn/{next_unit_id}{suffix}"
    if multiuser:
        return f"/dashboard{suffix}" if suffix else "/dashboard"
    return f"/{suffix}" if suffix else "/"


def _quote_user_id(request: Request | None) -> str:
    if request is None:
        return str(LOCAL_USER_ID)
    user = getattr(request.state, "current_user", None)
    if user is not None and getattr(user, "id", None) is not None:
        return str(user.id)
    return str(LOCAL_USER_ID)


def _format_review_date(value: date) -> str:
    return f"{value.day} {value.strftime('%B %Y')}"


def _ledger_line(progress: Any) -> str:
    if progress.status == "mastered" or progress.next_revision is None:
        return "No further reviews scheduled"
    return f"Next review · {_format_review_date(progress.next_revision)}"


def build_completion(
    *,
    eng: ReminderEngine,
    quotes: list[dict[str, str]],
    done_id: str | None,
    request: Request | None = None,
    is_guest: bool = False,
    today: date | None = None,
    continue_href: str | None = None,
    continue_label: str | None = None,
) -> dict[str, Any] | None:
    """Return template/JSON context only for a persisted completion today."""
    if not done_id or is_guest:
        return None
    today = today or date.today()
    unit = eng.get_unit(done_id)
    if unit is None:
        return None
    progress = eng.get_progress(done_id)
    if progress is None or progress.last_completed != today or progress.times_completed < 1:
        return None
    uid = _quote_user_id(request)
    seed = f"{uid}:{done_id}:{progress.last_completed}:{progress.times_completed}"
    quote = get_quote_for(quotes, seed)
    mastered = progress.status == "mastered" or progress.next_revision is None
    return {
        "unit_id": done_id,
        "article_ref": unit.display_title,
        "next_review": progress.next_revision,
        "status": progress.status,
        "mastered": mastered,
        "eyebrow": "Mastered" if mastered else "Review complete",
        "ledger": _ledger_line(progress),
        "quote": quote,
        "continue_href": continue_href or strip_done_param(""),
        "continue_label": continue_label,
    }


def done_json_payload(
    *,
    eng: ReminderEngine,
    quotes: list[dict[str, str]],
    unit: LearningUnit,
    result: Any,
    request: Request | None,
    multiuser: bool,
) -> dict[str, Any]:
    progress = result.progress
    next_url = next_learn_url(
        eng,
        result.next_unit_id,
        done_unit_id=unit.id,
        multiuser=multiuser,
    )
    next_unit = eng.get_unit(result.next_unit_id) if result.next_unit_id else None
    uid = _quote_user_id(request)
    seed = f"{uid}:{unit.id}:{progress.last_completed}:{progress.times_completed}"
    mastered = progress.status == "mastered" or progress.next_revision is None
    return {
        "ok": True,
        "next_url": next_url,
        "article_ref": unit.display_title,
        "next_review": (
            progress.next_revision.isoformat() if progress.next_revision else None
        ),
        "status": progress.status,
        "quote": get_quote_for(quotes, seed),
        "eyebrow": "Mastered" if mastered else "Review complete",
        "ledger": _ledger_line(progress),
        "continue_label": next_unit.display_title if next_unit is not None else None,
    }


def caught_up_quote(quotes: list[dict[str, str]], today: date | None = None) -> dict[str, str] | None:
    today = today or date.today()
    return get_quote_for(quotes, today.isoformat())

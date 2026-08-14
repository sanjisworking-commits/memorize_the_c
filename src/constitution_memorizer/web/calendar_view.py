"""Calendar month grid view-model for Learn progress."""

from __future__ import annotations

import calendar as pycal
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Literal

from constitution_memorizer.progress.repository import ProgressRecord
from constitution_memorizer.progress.scheduler import (
    INTERVAL_LADDER,
    ReminderEngine,
    advance_interval,
)

ChipKind = Literal["memorized", "review_done", "due", "scheduled"]

WEEKDAYS = ("Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat")


@dataclass(frozen=True)
class CalendarChip:
    kind: ChipKind
    unit_id: str
    label: str
    title: str


@dataclass
class CalendarDay:
    day: int | None
    iso: str | None
    is_today: bool = False
    is_past: bool = False
    is_blank: bool = False
    chips: list[CalendarChip] = field(default_factory=list)


@dataclass(frozen=True)
class CalendarMonth:
    year: int
    month: int
    title: str
    today: date
    prev_year: int
    prev_month: int
    next_year: int
    next_month: int
    summary: str
    weekdays: tuple[str, ...]
    days: list[CalendarDay]
    memorized_count: int
    review_done_count: int
    scheduled_count: int


def _shift_month(year: int, month: int, delta: int) -> tuple[int, int]:
    month += delta
    while month < 1:
        month += 12
        year -= 1
    while month > 12:
        month -= 12
        year += 1
    return year, month


def _chip_label(display_title: str) -> str:
    text = display_title.strip()
    if text.startswith("Article "):
        text = "Art " + text[len("Article ") :]
    if len(text) > 22:
        return text[:21] + "…"
    return text


def remaining_review_schedule(row: ProgressRecord) -> list[tuple[date, int]]:
    """
    Project remaining spaced-repetition dates for a progress row.

    Starts at ``next_revision`` (current rung = ``interval_days``), then assumes
    on-time completion for each later step of ``INTERVAL_LADDER``
    (1 → 3 → 7 → 14 → 30 → 60).
    """
    if row.next_revision is None or row.status not in ("review", "mastered"):
        return []
    cursor = row.next_revision
    current = row.interval_days if row.interval_days > 0 else INTERVAL_LADDER[0]
    out: list[tuple[date, int]] = [(cursor, current)]
    while True:
        nxt = advance_interval(current)
        if nxt is None:
            break
        cursor = cursor + timedelta(days=nxt)
        out.append((cursor, nxt))
        current = nxt
    return out


def completed_review_history(
    row: ProgressRecord,
) -> list[tuple[date, ChipKind, int | None]]:
    """
    Infer past completion days by walking ``INTERVAL_LADDER`` backwards from
    ``last_completed``.

    ``mark_done`` stores only the latest date, so the calendar reconstructs
    earlier rungs (memorize, then 1 → 3 → 7 → …) assuming on-time reviews.
    Late reviews shift inferred earlier dates.

    Each tuple is ``(when, kind, rung)`` where ``rung`` is the completed
    interval in days, or ``None`` for the first memorize.
    """
    if row.last_completed is None or row.times_completed < 1:
        return []
    n_reviews = min(row.times_completed - 1, len(INTERVAL_LADDER))
    rungs = INTERVAL_LADDER[:n_reviews]
    cursor = row.last_completed
    events: list[tuple[date, ChipKind, int | None]] = []
    for rung in reversed(rungs):
        events.append((cursor, "review_done", rung))
        cursor = cursor - timedelta(days=rung)
    events.append((cursor, "memorized", None))
    events.reverse()
    return events


def build_calendar_month(
    engine: ReminderEngine,
    *,
    year: int,
    month: int,
    today: date | None = None,
) -> CalendarMonth:
    """Build a Sunday-first month grid with progress + projected ladder chips."""
    if month < 1 or month > 12:
        raise ValueError("month must be 1–12")
    today = today or date.today()
    month_start = date(year, month, 1)
    last_day = pycal.monthrange(year, month)[1]
    month_end = date(year, month, last_day)

    # calendar.monthdayscalendar is Monday-first; convert to Sunday-first.
    cal = pycal.Calendar(firstweekday=6)
    weeks = cal.monthdayscalendar(year, month)

    by_day: dict[int, list[CalendarChip]] = {d: [] for d in range(1, last_day + 1)}
    memorized_count = 0
    review_done_count = 0
    scheduled_count = 0

    for row in engine.list_all_progress():
        unit = engine.get_unit(row.learning_unit_id)
        if unit is None:
            continue
        label = _chip_label(unit.display_title)
        full = unit.display_title

        for when, kind, rung in completed_review_history(row):
            if not (month_start <= when <= month_end):
                continue
            if kind == "memorized":
                memorized_count += 1
                tip = f"{full} — memorized"
                chip_label = label
            else:
                review_done_count += 1
                tip = (
                    f"{full} — {rung}-day review done"
                    if rung is not None
                    else f"{full} — review done"
                )
                chip_label = f"{label} ✓"
            by_day[when.day].append(
                CalendarChip(
                    kind=kind,
                    unit_id=row.learning_unit_id,
                    label=chip_label,
                    title=tip,
                )
            )

        for rev_date, rung in remaining_review_schedule(row):
            if not (month_start <= rev_date <= month_end):
                continue
            if rev_date <= today:
                # Only the actionable next_revision is due; skip past projections.
                if row.next_revision is None or rev_date != row.next_revision:
                    continue
                kind = "due"
                tip = f"{full} — {rung}-day review due"
            else:
                kind = "scheduled"
                tip = f"{full} — {rung}-day review"
                scheduled_count += 1
            by_day[rev_date.day].append(
                CalendarChip(
                    kind=kind,
                    unit_id=row.learning_unit_id,
                    label=label,
                    title=tip,
                )
            )

    days: list[CalendarDay] = []
    for week in weeks:
        for day_num in week:
            if day_num == 0:
                days.append(CalendarDay(day=None, iso=None, is_blank=True))
                continue
            d = date(year, month, day_num)
            days.append(
                CalendarDay(
                    day=day_num,
                    iso=d.isoformat(),
                    is_today=d == today,
                    is_past=d < today,
                    chips=by_day.get(day_num, []),
                )
            )

    prev_year, prev_month = _shift_month(year, month, -1)
    next_year, next_month = _shift_month(year, month, 1)
    title = month_start.strftime("%B %Y")
    summary = (
        f"{memorized_count} unit{'s' if memorized_count != 1 else ''} memorized this month · "
        f"{review_done_count} review{'s' if review_done_count != 1 else ''} completed · "
        f"{scheduled_count} review{'s' if scheduled_count != 1 else ''} scheduled"
    )
    return CalendarMonth(
        year=year,
        month=month,
        title=title,
        today=today,
        prev_year=prev_year,
        prev_month=prev_month,
        next_year=next_year,
        next_month=next_month,
        summary=summary,
        weekdays=WEEKDAYS,
        days=days,
        memorized_count=memorized_count,
        review_done_count=review_done_count,
        scheduled_count=scheduled_count,
    )

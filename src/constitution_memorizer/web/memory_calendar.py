"""Memory log month calendar — separate from Constitution /calendar."""

from __future__ import annotations

import calendar as pycal
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Literal

from constitution_memorizer.progress.memory import (
    MEMORY_INTERVAL_LADDER,
    MemoryEngine,
    MemoryEntry,
)

ChipKind = Literal["memorized", "review_done", "due", "scheduled"]
WEEKDAYS = ("Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat")


@dataclass(frozen=True)
class MemoryChip:
    kind: ChipKind
    entry_id: str
    label: str
    title: str


@dataclass
class MemoryDay:
    day: int | None
    iso: str | None
    is_today: bool = False
    is_past: bool = False
    is_blank: bool = False
    chips: list[MemoryChip] = field(default_factory=list)


@dataclass(frozen=True)
class MemoryMonth:
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
    days: list[MemoryDay]


def _shift_month(year: int, month: int, delta: int) -> tuple[int, int]:
    month += delta
    while month < 1:
        month += 12
        year -= 1
    while month > 12:
        month -= 12
        year += 1
    return year, month


def _short_label(title: str) -> str:
    text = title.strip()
    if len(text) > 18:
        return text[:17] + "…"
    return text


def schedule_chip_states(entry: MemoryEntry, *, today: date) -> list[tuple[int, str]]:
    """
    Ladder chip states for the detail page: done | due | upcoming.
    """
    del today  # rung state is driven by interval / mastery
    states: list[tuple[int, str]] = []
    for days in MEMORY_INTERVAL_LADDER:
        if entry.status == "mastered":
            states.append((days, "done"))
        elif entry.times_completed > 0 and days < entry.interval_days:
            states.append((days, "done"))
        elif days == entry.interval_days:
            states.append((days, "due"))
        else:
            states.append((days, "upcoming"))
    return states


def _review_kind(entry: MemoryEntry, rev_date: date, today: date) -> ChipKind:
    if entry.status == "mastered" or (
        entry.last_completed is not None and rev_date <= entry.last_completed
    ):
        return "review_done"
    if entry.next_revision == rev_date:
        return "due" if rev_date <= today else "scheduled"
    if rev_date > today:
        return "scheduled"
    # Past fixed marker: completed rungs behind current interval → done
    offset = (rev_date - entry.logged_date).days
    if entry.times_completed > 0 and offset < entry.interval_days:
        return "review_done"
    if rev_date <= today and entry.next_revision and entry.next_revision <= today:
        return "due" if rev_date >= entry.next_revision else "review_done"
    return "due" if rev_date <= today else "scheduled"


def build_memory_month(
    engine: MemoryEngine,
    *,
    year: int,
    month: int,
    today: date | None = None,
) -> MemoryMonth:
    today = today or date.today()
    if month < 1 or month > 12:
        raise ValueError("month must be 1–12")

    entries = engine.repo.list_all()
    chips_by_day: dict[str, list[MemoryChip]] = {}

    def add(iso: str, chip: MemoryChip) -> None:
        chips_by_day.setdefault(iso, []).append(chip)

    for entry in entries:
        if entry.logged_date.year == year and entry.logged_date.month == month:
            add(
                entry.logged_date.isoformat(),
                MemoryChip(
                    kind="memorized",
                    entry_id=entry.id,
                    label="★ " + _short_label(entry.title),
                    title=entry.title,
                ),
            )
        for days in MEMORY_INTERVAL_LADDER:
            rev_date = entry.logged_date + timedelta(days=days)
            if rev_date.year != year or rev_date.month != month:
                continue
            kind = _review_kind(entry, rev_date, today)
            label = _short_label(entry.title)
            if kind == "review_done":
                label = f"{label} ✓"
            add(
                rev_date.isoformat(),
                MemoryChip(
                    kind=kind,
                    entry_id=entry.id,
                    label=label,
                    title=entry.title,
                ),
            )

    cal = pycal.Calendar(firstweekday=6)
    days: list[MemoryDay] = []
    for week in cal.monthdayscalendar(year, month):
        for day_num in week:
            if day_num == 0:
                days.append(MemoryDay(day=None, iso=None, is_blank=True))
                continue
            d = date(year, month, day_num)
            iso = d.isoformat()
            days.append(
                MemoryDay(
                    day=day_num,
                    iso=iso,
                    is_today=d == today,
                    is_past=d < today,
                    chips=chips_by_day.get(iso, []),
                )
            )

    prev_y, prev_m = _shift_month(year, month, -1)
    next_y, next_m = _shift_month(year, month, 1)
    due_n = sum(
        1
        for e in entries
        if e.status != "mastered" and e.next_revision and e.next_revision <= today
    )
    return MemoryMonth(
        year=year,
        month=month,
        title=f"{pycal.month_name[month]} {year}",
        today=today,
        prev_year=prev_y,
        prev_month=prev_m,
        next_year=next_y,
        next_month=next_m,
        summary=f"{len(entries)} logged · {due_n} due for review",
        weekdays=WEEKDAYS,
        days=days,
    )

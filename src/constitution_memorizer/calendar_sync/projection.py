"""Project the persisted revision schedule into per-day calendar workload.

Pure translation layer: reads ``learning_unit_progress`` rows through the
user-bound engine and groups them by their stored ``next_revision`` date.
It never computes revision dates itself — the ladder lives in
``progress/scheduler.py`` alone. Stored dates are authoritative local dates
and are never timezone-rebucketed; the timezone only decides each event's
clock time and the meaning of "today" for overdue rollup.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date, timedelta

from constitution_memorizer.learning.schemas import LearningUnitType
from constitution_memorizer.progress.scheduler import ReminderEngine
from constitution_memorizer.web.service import unit_visible_for_preference

# The ladder's longest rung is 60 days; 90 covers every reachable future date.
PROJECTION_HORIZON_DAYS = 90
# Cap description lines so a heavy day doesn't produce an unwieldy event.
MAX_DESCRIPTION_ITEMS = 15

EVENT_TITLE_PREFIX = "🧠 Recall the C"


@dataclass(frozen=True)
class DayItem:
    """One unit's revision appearing on a projected day."""

    unit_id: str
    label: str  # e.g. "Article 14 — Day 15"


@dataclass(frozen=True)
class DayProjection:
    local_date: date
    items: list[DayItem] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.items)


def _day_label(unit_title: str, interval_days: int) -> str:
    if interval_days > 0:
        return f"{unit_title} — Day {interval_days}"
    return unit_title


def build_projection(
    engine: ReminderEngine,
    *,
    today: date,
    horizon_days: int = PROJECTION_HORIZON_DAYS,
) -> dict[date, DayProjection]:
    """Group upcoming (and overdue) revisions by their stored local date.

    Overdue revisions (stored date < today) roll INTO today — that mirrors the
    dashboard's due list, which surfaces everything due-or-overdue now. Dates
    beyond the horizon are ignored (nothing reachable lives there).
    """
    end = today + timedelta(days=horizon_days)
    buckets: dict[date, list[DayItem]] = {}
    for record in engine.repo.list_all_progress(engine.user_id):
        if record.next_revision is None or record.status == "mastered":
            continue
        unit = engine.get_unit(record.learning_unit_id)
        if unit is None or unit.type == LearningUnitType.PART_OVERVIEW:
            continue
        if not unit_visible_for_preference(engine, unit):
            continue
        target = record.next_revision if record.next_revision > today else today
        if target > end:
            continue
        buckets.setdefault(target, []).append(
            DayItem(
                unit_id=record.learning_unit_id,
                label=_day_label(unit.display_title, record.interval_days),
            )
        )
    return {
        d: DayProjection(local_date=d, items=sorted(items, key=lambda i: i.label))
        for d, items in buckets.items()
    }


@dataclass(frozen=True)
class EventContent:
    """Everything Google sees for one day's event."""

    local_date: date
    title: str
    description: str
    start_time: str  # "HH:MM" local
    duration_minutes: int
    timezone: str  # IANA id
    url: str

    def payload_hash(self) -> str:
        """Hash of the FULL payload — time/duration/tz/url changes dirty it."""
        blob = json.dumps(
            {
                "date": self.local_date.isoformat(),
                "title": self.title,
                "description": self.description,
                "start": self.start_time,
                "minutes": self.duration_minutes,
                "tz": self.timezone,
                "url": self.url,
            },
            sort_keys=True,
        )
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def build_event_content(
    day: DayProjection,
    *,
    revision_time: str,
    session_minutes: int,
    timezone: str,
    dashboard_url: str,
) -> EventContent:
    n = day.count
    title = f"{EVENT_TITLE_PREFIX} — {n} revision{'s' if n != 1 else ''}"
    lines = [f"{n} revision{'s' if n != 1 else ''} scheduled today.", ""]
    shown = day.items[:MAX_DESCRIPTION_ITEMS]
    lines.extend(item.label for item in shown)
    remaining = n - len(shown)
    if remaining > 0:
        lines.append(f"+ {remaining} more")
    lines.extend(["", "Start today's revisions:", dashboard_url])
    return EventContent(
        local_date=day.local_date,
        title=title,
        description="\n".join(lines),
        start_time=revision_time,
        duration_minutes=session_minutes,
        timezone=timezone,
        url=dashboard_url,
    )

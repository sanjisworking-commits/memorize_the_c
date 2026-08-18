"""Calendar projection: grouping, filtering, labels, hashes, tz invariance."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from constitution_memorizer.calendar_sync.projection import (
    DayItem,
    DayProjection,
    build_event_content,
    build_projection,
)
from constitution_memorizer.progress.scheduler import ReminderEngine

MINI_UNITS = Path(__file__).parent / "fixtures" / "learning" / "mini_units.json"


def _engine(tmp_path: Path) -> ReminderEngine:
    return ReminderEngine.from_paths(tmp_path / "progress.db", MINI_UNITS)


def _complete(engine: ReminderEngine, unit_id: str, on: date) -> None:
    engine.mark_all_modes_seen(unit_id)
    engine.mark_done(unit_id, as_of=on)


def test_empty_projection(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    assert build_projection(engine, today=date(2026, 8, 18)) == {}


def test_single_revision_grouped_on_stored_date(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    _complete(engine, "clause-1", date(2026, 8, 18))
    projection = build_projection(engine, today=date(2026, 8, 18))
    assert list(projection) == [date(2026, 8, 19)]  # +1 day rung
    day = projection[date(2026, 8, 19)]
    assert day.count == 1
    assert day.items[0].unit_id == "clause-1"
    assert day.items[0].label.endswith("— Day 1")


def test_overdue_rolls_into_today(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    _complete(engine, "clause-1", date(2026, 8, 1))  # due 2 Aug
    today = date(2026, 8, 18)
    projection = build_projection(engine, today=today)
    assert list(projection) == [today]


def test_mastered_and_horizon_excluded(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    # Climb the whole ladder → mastered (no future date).
    on = date(2026, 1, 1)
    for _ in range(7):
        _complete(engine, "clause-1", on)
    row = engine.get_progress("clause-1")
    assert row is not None and row.status == "mastered"
    assert build_projection(engine, today=date(2026, 8, 18)) == {}


def test_stored_date_is_timezone_invariant(tmp_path: Path) -> None:
    """A stored next_revision of 20 Aug is 20 Aug in Kolkata AND New York —
    the projection never rebuckets dates; only event clock time uses the tz."""
    engine = _engine(tmp_path)
    _complete(engine, "clause-1", date(2026, 8, 19))  # → due 20 Aug
    projection = build_projection(engine, today=date(2026, 8, 19))
    assert list(projection) == [date(2026, 8, 20)]

    day = projection[date(2026, 8, 20)]
    for tz in ("Asia/Kolkata", "America/New_York"):
        content = build_event_content(
            day,
            revision_time="20:00",
            session_minutes=30,
            timezone=tz,
            dashboard_url="https://recall-the-c.in/dashboard",
        )
        assert content.local_date == date(2026, 8, 20)
        assert content.timezone == tz


def test_event_content_and_description_cap() -> None:
    items = [DayItem(unit_id=f"u{i}", label=f"Article {i} — Day 3") for i in range(20)]
    day = DayProjection(local_date=date(2026, 8, 24), items=items)
    content = build_event_content(
        day,
        revision_time="20:00",
        session_minutes=45,
        timezone="Asia/Kolkata",
        dashboard_url="https://recall-the-c.in/dashboard",
    )
    assert content.title == "🧠 Recall the C — 20 revisions"
    assert "20 revisions scheduled today." in content.description
    assert "+ 5 more" in content.description  # capped at 15 lines
    assert "https://recall-the-c.in/dashboard" in content.description
    assert content.duration_minutes == 45


def test_payload_hash_dirties_on_every_visible_field() -> None:
    day = DayProjection(
        local_date=date(2026, 8, 24),
        items=[DayItem(unit_id="u1", label="Article 14 — Day 15")],
    )
    base = dict(
        revision_time="20:00",
        session_minutes=30,
        timezone="Asia/Kolkata",
        dashboard_url="https://recall-the-c.in/dashboard",
    )
    baseline = build_event_content(day, **base).payload_hash()
    # Stable when nothing changes.
    assert build_event_content(day, **base).payload_hash() == baseline
    # Time, duration, timezone, and URL each dirty the hash.
    for change in (
        {"revision_time": "21:00"},
        {"session_minutes": 45},
        {"timezone": "Europe/London"},
        {"dashboard_url": "https://recall-the-c.in/other"},
    ):
        assert (
            build_event_content(day, **{**base, **change}).payload_hash() != baseline
        )

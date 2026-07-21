"""Sprint 26 — notification schedule gate."""

from __future__ import annotations

from datetime import datetime

from constitution_memorizer.notifications.schedule import should_notify


def _dt(hour: int, day: int = 20) -> datetime:
    return datetime(2026, 7, day, hour, 0, 0)


def test_nothing_due_never_sends():
    d = should_notify(
        frequency="hourly",
        now=_dt(10),
        due_count=0,
        last_slot=None,
    )
    assert d.should_send is False
    assert "nothing due" in d.reason


def test_thrice_wrong_hour_skips():
    d = should_notify(
        frequency="thrice",
        now=_dt(10),
        due_count=2,
        last_slot=None,
    )
    assert d.should_send is False
    assert "not a reminder hour" in d.reason


def test_thrice_slot_fires():
    d = should_notify(
        frequency="thrice",
        now=_dt(13),
        due_count=1,
        last_slot=None,
    )
    assert d.should_send is True
    assert "thrice" in d.reason


def test_twice_slots():
    assert should_notify(
        frequency="twice", now=_dt(8), due_count=1, last_slot=None
    ).should_send
    assert should_notify(
        frequency="twice", now=_dt(18), due_count=1, last_slot=None
    ).should_send
    assert not should_notify(
        frequency="twice", now=_dt(13), due_count=1, last_slot=None
    ).should_send


def test_same_hour_debounce():
    last = _dt(8)
    d = should_notify(
        frequency="thrice",
        now=_dt(8, day=20),
        due_count=3,
        last_slot=last,
    )
    assert d.should_send is False
    assert "already sent" in d.reason


def test_hourly_while_due():
    d = should_notify(
        frequency="hourly",
        now=_dt(11),
        due_count=2,
        last_slot=_dt(10),
    )
    assert d.should_send is True


def test_hourly_stops_when_empty():
    d = should_notify(
        frequency="hourly",
        now=_dt(11),
        due_count=0,
        last_slot=_dt(10),
    )
    assert d.should_send is False

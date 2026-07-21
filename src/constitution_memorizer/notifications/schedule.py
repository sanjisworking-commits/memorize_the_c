"""Decide whether this hourly tick should send a study reminder."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

NotificationFrequency = Literal["twice", "thrice", "hourly"]

# Local clock hours for fixed cadences.
SLOTS: dict[str, tuple[int, ...]] = {
    "twice": (8, 18),
    "thrice": (8, 13, 18),
    "hourly": (),
}


@dataclass(frozen=True)
class NotifyDecision:
    should_send: bool
    reason: str


def _same_local_hour(a: datetime, b: datetime) -> bool:
    return a.year == b.year and a.month == b.month and a.day == b.day and a.hour == b.hour


def should_notify(
    *,
    frequency: NotificationFrequency | str,
    now: datetime,
    due_count: int,
    last_slot: datetime | None,
) -> NotifyDecision:
    """
    Gate hourly LaunchAgent ticks against Settings cadence + due list.

    - Nothing due → never send (hourly stops when today's checklist is empty).
    - twice/thrice → only at configured local hours, once per hour.
    - hourly → every local hour while due_count > 0, once per hour.
    """
    if due_count <= 0:
        return NotifyDecision(False, "nothing due")

    if last_slot is not None and _same_local_hour(last_slot, now):
        return NotifyDecision(False, "already sent this hour")

    if frequency == "hourly":
        return NotifyDecision(True, "hourly nag")

    slots = SLOTS.get(frequency)
    if slots is None:
        return NotifyDecision(False, f"unknown frequency: {frequency}")

    if now.hour not in slots:
        hours = ", ".join(f"{h:02d}:00" for h in slots)
        return NotifyDecision(False, f"not a reminder hour (slots {hours})")

    return NotifyDecision(True, f"{frequency} slot {now.hour:02d}:00")

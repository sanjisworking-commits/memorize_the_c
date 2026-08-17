"""Recall pricing model — one product, seven durations, single source of truth.

Every paid duration unlocks exactly the same complete Recall experience; only
the access period (and its renewal behaviour) differs. Feature code must never
branch on a specific duration — while a plan is active the user simply resolves
to ``subscribed`` access.

Durations of 15 days or less are one-time access passes (no automatic
renewal); longer durations auto-renew until cancelled. Prices are provisional
and centralized here — one edit updates the page, the client data, and tests.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RecallPlan:
    days: int
    price_inr: int
    tagline: str
    annotation: str | None
    recurring: bool


PLANS: tuple[RecallPlan, ...] = (
    RecallPlan(
        days=3,
        price_inr=49,
        tagline="A short sprint to test your recall habit.",
        annotation=None,
        recurring=False,
    ),
    RecallPlan(
        days=7,
        price_inr=99,
        tagline="A focused week on the Articles that matter now.",
        annotation=None,
        recurring=False,
    ),
    RecallPlan(
        days=15,
        price_inr=149,
        tagline="A fortnight to build a steady revision rhythm.",
        annotation=None,
        recurring=False,
    ),
    RecallPlan(
        days=30,
        price_inr=199,
        tagline="A flexible month — learn at your own pace.",
        annotation="Most flexible",
        recurring=True,
    ),
    RecallPlan(
        days=60,
        price_inr=299,
        tagline="Two months to move from reading to recall.",
        annotation=None,
        recurring=True,
    ),
    RecallPlan(
        days=180,
        price_inr=699,
        tagline="Designed for the complete Constitution memory journey.",
        annotation="Complete Recall journey",
        recurring=True,
    ),
    RecallPlan(
        days=365,
        price_inr=999,
        tagline="A full year of Recall at the best daily value.",
        annotation="Best daily value",
        recurring=True,
    ),
)

# Progressive disclosure: primary rail first, "More options" reveals the rest.
PRIMARY_DAYS: tuple[int, ...] = (7, 30, 180, 365)
MORE_DAYS: tuple[int, ...] = (3, 15, 60)

# The hero duration — the complete Recall journey.
DEFAULT_DAYS = 180

_BY_DAYS = {plan.days: plan for plan in PLANS}


def per_day(plan: RecallPlan) -> float:
    """Effective daily rate, rounded to paise."""
    return round(plan.price_inr / plan.days, 2)


def get_plan(days: object) -> RecallPlan:
    """Look a plan up by days; unknown/invalid values fall back to the hero."""
    try:
        return _BY_DAYS[int(days)]  # type: ignore[arg-type]
    except (KeyError, TypeError, ValueError):
        return _BY_DAYS[DEFAULT_DAYS]


def billing_line(plan: RecallPlan) -> str:
    """The one place billing copy derives from ``recurring``."""
    if plan.recurring:
        return f"Renews every {plan.days} days · Cancel anytime"
    return f"{plan.days}-day access · No automatic renewal"


def plans_json() -> list[dict[str, object]]:
    """Client payload for the pricing page's no-reload selector."""
    return [
        {
            "days": plan.days,
            "price_inr": plan.price_inr,
            "per_day": per_day(plan),
            "tagline": plan.tagline,
            "annotation": plan.annotation,
            "recurring": plan.recurring,
            "billing_line": billing_line(plan),
        }
        for plan in PLANS
    ]

"""Central access / entitlement service.

Single source of truth for *who* a request belongs to (``guest`` / ``free`` /
``subscribed``) and, for a given parent Article, *what they may do* (which Learn
modes are open, what Done requires, whether pressing Done should claim a Free
Article or hit the subscription gate).

Every surface — Learn routes, Done, templates, and JS payloads — consumes the
result of :func:`compute_learn_access` / :func:`access_summary` rather than
re-deriving quota or mode rules. Feature code asks a capability; it never
branches on a specific paid duration.

Roadmap note: this module is pure logic + light request/engine resolvers. The
Learn locks (step 3) and Article-aware Done (step 4) wire it into the routes;
here (step 1) it powers only read-only status surfaces. ``is_subscribed`` is the
billing seam filled in step 6 — until then it is always ``False``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

# Modes always available (guest / free-cap-reached still get these four).
OPEN_MODES: tuple[str, ...] = ("read", "cloze", "letters", "card")
# Subscriber-only modes (locked for guest and free-cap-reached).
SUBSCRIBER_ONLY_MODES: tuple[str, ...] = ("type", "recite")
# Canonical render order of all six modes.
ALL_MODES: tuple[str, ...] = ("read", "cloze", "letters", "type", "recite", "card")

# A signed-in Free account may permanently claim this many parent Articles.
FREE_ARTICLE_LIMIT = 3

# Access levels.
GUEST = "guest"
FREE = "free"
SUBSCRIBED = "subscribed"


def entitlements_active(request: object) -> bool:
    """Whether the 3-Free-Article boundary is switched on for this app.

    ``ARTICLE_ENTITLEMENTS_ENABLED`` defaults to false everywhere; steps 1–4 of
    the entitlement roadmap land progressively but stay dormant behind it. With
    the flag off, every caller sees legacy behavior (all six modes, no claim
    prompts, no gates, no status surfaces) and no entitlement DB reads happen.
    """
    app_state = getattr(getattr(request, "app", None), "state", None)
    return bool(getattr(app_state, "article_entitlements_enabled", False))


def article_key(article_number: object) -> str | None:
    """Normalize a parent Article number to the string key used everywhere.

    Returns ``None`` for units with no Article (nothing to claim / gate).
    """
    if article_number is None:
        return None
    key = str(article_number).strip()
    return key or None


# --------------------------------------------------------------------------- #
# Access level                                                                 #
# --------------------------------------------------------------------------- #
def is_subscribed(user: object) -> bool:
    """Billing seam. Always ``False`` until the payment layer lands (step 6)."""
    return False


def resolve_level(*, multiuser_enabled: bool, has_user: bool, subscribed: bool) -> str:
    """Pure access-level resolution (unit-testable without a request).

    - multiuser off  -> local single-user owner keeps full access (``subscribed``)
    - no signed-in user -> ``guest``
    - signed-in + active subscription -> ``subscribed``; else ``free``
    """
    if not multiuser_enabled:
        return SUBSCRIBED
    if not has_user:
        return GUEST
    return SUBSCRIBED if subscribed else FREE


def access_level(request: object) -> str:
    """Resolve the access level for a FastAPI request."""
    app_state = getattr(getattr(request, "app", None), "state", None)
    multiuser_enabled = bool(getattr(app_state, "multiuser_enabled", False))
    user = getattr(getattr(request, "state", None), "current_user", None)
    return resolve_level(
        multiuser_enabled=multiuser_enabled,
        has_user=user is not None,
        subscribed=user is not None and is_subscribed(user),
    )


# --------------------------------------------------------------------------- #
# Per-Article Learn access                                                      #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class LearnAccess:
    """What the current user may do on one parent Article.

    Persistence matrix (R2·3): claimed/subscribed Articles persist
    ``modes_seen`` server-side; a claimable-but-unclaimed Article is
    *provisional* Learn state (client-tracked until claim-on-Done);
    cap-reached unclaimed Articles and guests are local/exploratory only.
    """

    level: str
    article_claimed: bool
    free_slots_remaining: int
    allowed_modes: tuple[str, ...]
    required_modes: tuple[str, ...]
    locked_modes: tuple[str, ...]
    can_persist_modes_seen: bool
    can_persist_done: bool
    should_prompt_claim: bool
    cap_reached: bool

    def is_locked(self, mode: str) -> bool:
        return mode in self.locked_modes


def _full_access(level: str, *, article_claimed: bool, slots: int) -> LearnAccess:
    return LearnAccess(
        level=level,
        article_claimed=article_claimed,
        free_slots_remaining=slots,
        allowed_modes=ALL_MODES,
        required_modes=ALL_MODES,
        locked_modes=(),
        can_persist_modes_seen=True,
        can_persist_done=True,
        should_prompt_claim=False,
        cap_reached=False,
    )


def compute_learn_access(
    level: str,
    *,
    article_claimed: bool = False,
    free_slots_remaining: int = 0,
) -> LearnAccess:
    """Pure Article-aware access calculation (no request/DB dependency).

    Matrix:
      guest             -> 4 open modes, Type/Recite locked, Done local-only
      free + claimed    -> all 6, Done requires 6, persists
      free + claimable  -> all 6, Done requires 6, prompts claim, persists on confirm
      free + cap-reached-> 4 open modes, Type/Recite locked, Done -> gate, no persist
      subscribed        -> all 6 everywhere, persists
    """
    if level == SUBSCRIBED:
        return _full_access(SUBSCRIBED, article_claimed=article_claimed, slots=free_slots_remaining)

    if level == GUEST:
        return LearnAccess(
            level=GUEST,
            article_claimed=False,
            free_slots_remaining=0,
            allowed_modes=OPEN_MODES,
            required_modes=OPEN_MODES,
            locked_modes=SUBSCRIBER_ONLY_MODES,
            can_persist_modes_seen=False,
            can_persist_done=False,
            should_prompt_claim=False,
            cap_reached=False,
        )

    # level == FREE
    if article_claimed:
        return _full_access(FREE, article_claimed=True, slots=free_slots_remaining)
    if free_slots_remaining > 0:
        # Claimable: all six open, but nothing becomes permanent account
        # progress until the learner confirms the claim on Done — mode visits
        # stay provisional (client-tracked) until then.
        return LearnAccess(
            level=FREE,
            article_claimed=False,
            free_slots_remaining=free_slots_remaining,
            allowed_modes=ALL_MODES,
            required_modes=ALL_MODES,
            locked_modes=(),
            can_persist_modes_seen=False,
            can_persist_done=True,
            should_prompt_claim=True,
            cap_reached=False,
        )
    # Free, unclaimed, no slots left -> cap reached. The four open modes are
    # exploration only; they never quietly become saved progress.
    return LearnAccess(
        level=FREE,
        article_claimed=False,
        free_slots_remaining=0,
        allowed_modes=OPEN_MODES,
        required_modes=OPEN_MODES,
        locked_modes=SUBSCRIBER_ONLY_MODES,
        can_persist_modes_seen=False,
        can_persist_done=False,
        should_prompt_claim=False,
        cap_reached=True,
    )


def resolve_learn_access(request: object, engine: object, article_number: object) -> LearnAccess:
    """Resolve :class:`LearnAccess` from a request + the per-user engine.

    While ``ARTICLE_ENTITLEMENTS_ENABLED`` is off, every request resolves to
    full legacy access (all six modes, everything persists, no prompts) and no
    entitlement store reads happen.
    """
    level = access_level(request)
    if not entitlements_active(request):
        return _full_access(level, article_claimed=False, slots=FREE_ARTICLE_LIMIT)
    if level != FREE:
        return compute_learn_access(level)
    claimed = _claimed_articles(engine)
    key = article_key(article_number)
    return compute_learn_access(
        FREE,
        article_claimed=key is not None and key in claimed,
        free_slots_remaining=max(0, FREE_ARTICLE_LIMIT - len(claimed)),
    )


# --------------------------------------------------------------------------- #
# Account / surface status                                                      #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class AccessSummary:
    """Read-only access status shown on Profile / Settings / Dashboard."""

    level: str
    claimed_count: int
    free_slots_remaining: int
    claimed_articles: tuple[str, ...]
    cap_reached: bool
    is_subscribed: bool
    # False while ARTICLE_ENTITLEMENTS_ENABLED is off — surfaces render nothing.
    enabled: bool = True
    # Grandfathered accounts may hold more than the 3-slot limit permanently.
    legacy_over_cap: bool = False
    # Filled from the billing layer in step 7; None until then.
    subscription_label: str | None = None
    renews_or_expires_on: str | None = None

    @property
    def is_free(self) -> bool:
        return self.level == FREE

    @property
    def status_line(self) -> str:
        """Compact one-line status for Settings / Dashboard chip."""
        if self.level == SUBSCRIBED:
            if self.subscription_label:
                return f"Recall active · {self.subscription_label}"
            return "Recall active"
        if self.level == GUEST:
            return "Guest"
        if self.legacy_over_cap:
            return f"Free · {self.claimed_count} saved Articles · Legacy access"
        return f"Free · {self.claimed_count} of {FREE_ARTICLE_LIMIT} Articles"


_DISABLED_SUMMARY = AccessSummary(
    level=FREE,
    claimed_count=0,
    free_slots_remaining=FREE_ARTICLE_LIMIT,
    claimed_articles=(),
    cap_reached=False,
    is_subscribed=False,
    enabled=False,
)


def build_access_summary(
    level: str,
    *,
    claimed_articles: Iterable[str] = (),
    subscribed: bool = False,
) -> AccessSummary:
    """Pure account-summary construction (unit-testable)."""
    claimed = tuple(claimed_articles)
    count = len(claimed)
    slots = max(0, FREE_ARTICLE_LIMIT - count)
    return AccessSummary(
        level=level,
        claimed_count=count,
        free_slots_remaining=slots,
        claimed_articles=claimed,
        cap_reached=(level == FREE and slots == 0),
        is_subscribed=subscribed,
        legacy_over_cap=(level == FREE and count > FREE_ARTICLE_LIMIT),
    )


def access_summary(request: object, engine: object) -> AccessSummary:
    """Resolve the account summary from a request + per-user engine.

    Returns a disabled marker (no DB reads) while the entitlement boundary is
    dormant, so status surfaces stay hidden and query load is unchanged.
    """
    if not entitlements_active(request):
        return _DISABLED_SUMMARY
    level = access_level(request)
    if level == GUEST:
        return build_access_summary(GUEST)
    claimed = sorted(_claimed_articles(engine), key=_article_sort_key)
    return build_access_summary(level, claimed_articles=claimed, subscribed=(level == SUBSCRIBED))


# --------------------------------------------------------------------------- #
# Engine helpers (tolerant of an engine without the store yet)                  #
# --------------------------------------------------------------------------- #
def _claimed_articles(engine: object) -> set[str]:
    getter = getattr(engine, "claimed_articles", None)
    if getter is None:
        return set()
    try:
        return set(getter())
    except Exception:  # pragma: no cover - defensive; store not ready
        return set()


def _article_sort_key(value: str) -> tuple[int, object]:
    """Sort Article keys numerically when possible, else lexicographically."""
    try:
        return (0, int(value))
    except (TypeError, ValueError):
        return (1, str(value))

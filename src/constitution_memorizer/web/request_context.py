"""Per-request bound engine/memory and diagnostic timings."""

from __future__ import annotations

from contextvars import ContextVar, Token
from time import perf_counter
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from constitution_memorizer.progress.memory import MemoryEngine
    from constitution_memorizer.progress.scheduler import ReminderEngine

bound_engine: ContextVar[ReminderEngine | None] = ContextVar("bound_engine", default=None)
bound_memory: ContextVar[MemoryEngine | None] = ContextVar("bound_memory", default=None)

# stage -> (total_ms, call_count). None = no HTTP request collector bound.
_request_timings: ContextVar[dict[str, tuple[float, int]] | None] = ContextVar(
    "request_timings", default=None
)

TIMING_STAGES: tuple[str, ...] = (
    "auth_session",
    "profile",
    "progress_preload",
    "split_prefs",
    "news_setting",
    "browse_build",
    "dashboard_build",
    "completion",
    "modes_seen",
    "theme",
    "nav_due",
    "template",
)

_TIMING_STAGE_SET = frozenset(TIMING_STAGES)


def begin_request_timings() -> Token:
    """Bind an empty collector for this request. Returns a reset token."""
    return _request_timings.set({})


def reset_request_timings(token: Token) -> None:
    """Restore the previous collector binding."""
    _request_timings.reset(token)


def snapshot_request_timings() -> dict[str, tuple[float, int]]:
    """Independent copy of recorded stages, or {} if no collector is bound."""
    current = _request_timings.get()
    if current is None:
        return {}
    return dict(current)


def record_request_timing(stage: str, started: float) -> None:
    """Accumulate elapsed ms for a whitelisted stage. No-op outside a request."""
    if stage not in _TIMING_STAGE_SET:
        raise ValueError(f"Unknown request timing stage: {stage}")
    current = _request_timings.get()
    if current is None:
        return
    elapsed_ms = (perf_counter() - started) * 1000.0
    total_ms, count = current.get(stage, (0.0, 0))
    current[stage] = (total_ms + elapsed_ms, count + 1)

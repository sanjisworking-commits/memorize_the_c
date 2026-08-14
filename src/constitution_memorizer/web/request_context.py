"""Per-request bound engine/memory (set by auth middleware)."""

from __future__ import annotations

from contextvars import ContextVar
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from constitution_memorizer.progress.memory import MemoryEngine
    from constitution_memorizer.progress.scheduler import ReminderEngine

bound_engine: ContextVar[ReminderEngine | None] = ContextVar("bound_engine", default=None)
bound_memory: ContextVar[MemoryEngine | None] = ContextVar("bound_memory", default=None)

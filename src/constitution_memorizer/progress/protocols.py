"""Repository protocols for user-scoped personal data."""

from __future__ import annotations

from datetime import date
from typing import Protocol
from uuid import UUID

from constitution_memorizer.progress.repository import ProgressRecord, ProgressStatus, SplitMode


class ProgressRepositoryProtocol(Protocol):
    def get_progress(
        self, user_id: UUID, learning_unit_id: str
    ) -> ProgressRecord | None: ...

    def save_progress(self, user_id: UUID, progress: ProgressRecord) -> None: ...

    def list_due(self, user_id: UUID, as_of: date) -> list[ProgressRecord]: ...

    def get_split_preference(
        self, user_id: UUID, parent_clause_id: str
    ) -> SplitMode | None: ...


# Alias matching the plan naming.
class ProgressRepository(ProgressRepositoryProtocol, Protocol):
    def get_progress(
        self,
        user_id: UUID,
        learning_unit_id: str,
    ) -> ProgressRecord | None: ...

    def save_progress(
        self,
        user_id: UUID,
        progress: ProgressRecord,
    ) -> None: ...

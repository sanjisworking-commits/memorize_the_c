"""Request-scoped ReminderEngine caches avoid per-unit get_progress N+1."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from uuid import UUID, uuid4

from constitution_memorizer.learning.schemas import LearningUnitsDocument
from constitution_memorizer.progress.repository import ProgressRepository
from constitution_memorizer.progress.scheduler import ReminderEngine
from constitution_memorizer.progress.db import open_progress_db
from constitution_memorizer.utils.json_io import read_json

MINI_UNITS = Path(__file__).parent / "fixtures" / "learning" / "mini_units.json"
USER = UUID("11111111-1111-4111-8111-111111111111")


class CountingProgressRepo:
    """Wraps a real SQLite repo and counts get_progress / list_all_progress."""

    def __init__(self, inner: ProgressRepository) -> None:
        self.inner = inner
        self.get_progress_calls = 0
        self.list_all_progress_calls = 0
        self.list_split_preferences_calls = 0
        self.get_split_preference_calls = 0

    def __getattr__(self, name: str):
        return getattr(self.inner, name)

    def get_progress(self, user_id, unit_id: str):
        self.get_progress_calls += 1
        return self.inner.get_progress(user_id, unit_id)

    def list_all_progress(self, user_id):
        self.list_all_progress_calls += 1
        return self.inner.list_all_progress(user_id)

    def list_split_preferences(self, user_id):
        self.list_split_preferences_calls += 1
        return self.inner.list_split_preferences(user_id)

    def get_split_preference(self, user_id, parent_clause_id: str):
        self.get_split_preference_calls += 1
        return self.inner.get_split_preference(user_id, parent_clause_id)


def _catalog() -> dict:
    doc = LearningUnitsDocument.model_validate(read_json(MINI_UNITS))
    return {u.id: u for u in doc.units}


def test_dashboard_style_iteration_uses_one_list_all_progress(tmp_path: Path):
    conn = open_progress_db(tmp_path / "progress.db")
    inner = ProgressRepository(conn)
    repo = CountingProgressRepo(inner)
    catalog = _catalog()
    unit_ids = list(catalog)[:8]
    assert len(unit_ids) >= 3

    seed = ReminderEngine.from_repository(repo, catalog, user_id=USER)
    for unit_id in unit_ids[:3]:
        seed.mark_all_modes_seen(unit_id)
        seed.mark_done(unit_id, as_of=date(2026, 8, 1))

    # Fresh request-bound engine (as auth middleware does via for_user).
    app_engine = ReminderEngine.from_repository(repo, catalog, user_id=uuid4())
    bound = app_engine.for_user(USER)
    repo.get_progress_calls = 0
    repo.list_all_progress_calls = 0

    # Simulate Dashboard/Browse/Progress iterating every unit.
    for unit_id in catalog:
        bound.get_progress(unit_id)

    assert repo.get_progress_calls == 0
    assert repo.list_all_progress_calls == 1
    # Second pass must not reload.
    for unit_id in catalog:
        bound.get_progress(unit_id)
    assert repo.list_all_progress_calls == 1


def test_for_user_starts_with_empty_cache(tmp_path: Path):
    conn = open_progress_db(tmp_path / "progress.db")
    repo = CountingProgressRepo(ProgressRepository(conn))
    catalog = _catalog()
    root = ReminderEngine.from_repository(repo, catalog, user_id=USER)
    # Warm root cache.
    root.get_progress(next(iter(catalog)))
    assert repo.list_all_progress_calls == 1

    bound = root.for_user(USER)
    assert bound._progress_cache is None
    assert bound._split_cache is None
    bound.get_progress(next(iter(catalog)))
    assert repo.list_all_progress_calls == 2


def test_write_updates_progress_cache_without_stale_reads(tmp_path: Path):
    conn = open_progress_db(tmp_path / "progress.db")
    repo = CountingProgressRepo(ProgressRepository(conn))
    catalog = _catalog()
    unit_id = next(iter(catalog))
    engine = ReminderEngine.from_repository(repo, catalog, user_id=USER)
    assert engine.get_progress(unit_id) is None
    engine.mark_all_modes_seen(unit_id)
    result = engine.mark_done(unit_id, as_of=date(2026, 8, 1))
    cached = engine.get_progress(unit_id)
    assert cached is not None
    assert cached.status == result.progress.status
    assert cached.times_completed == result.progress.times_completed
    # No per-get_progress repo hits after cache warm + write store.
    before = repo.get_progress_calls
    assert engine.get_progress(unit_id) is not None
    assert repo.get_progress_calls == before


def test_split_preference_cache_and_invalidation(tmp_path: Path):
    conn = open_progress_db(tmp_path / "progress.db")
    repo = CountingProgressRepo(ProgressRepository(conn))
    catalog = _catalog()
    parent = next(
        (u.id for u in catalog.values() if u.allows_letter_split),
        next(iter(catalog)),
    )
    engine = ReminderEngine.from_repository(repo, catalog, user_id=USER)
    assert engine.get_split_preference(parent) is None
    assert repo.list_split_preferences_calls == 1
    assert repo.get_split_preference_calls == 0

    engine.set_split_preference(parent, "letters")
    assert engine.get_split_preference(parent) == "letters"
    assert repo.list_split_preferences_calls == 1

    engine.delete_split_preference(parent)
    assert engine.get_split_preference(parent) is None

    engine.reset_all_personal_data()
    assert engine._progress_cache is None
    assert engine._split_cache is None

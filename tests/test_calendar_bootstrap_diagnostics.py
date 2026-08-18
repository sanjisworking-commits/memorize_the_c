"""Leaf request timings for entitlements, Settings, and Calendar bootstrap."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID

from constitution_memorizer.admin.dependencies import admin_hint, resolve_access_override
from constitution_memorizer.admin.store import AccessOverride, AdminHintCache
from constitution_memorizer.web.entitlements import subscription_status
from constitution_memorizer.web.request_context import (
    begin_request_timings,
    reset_request_timings,
    snapshot_request_timings,
)
from tests.test_request_bootstrap import _seeded_engine

USER = UUID("11111111-1111-4111-8111-111111111111")


class CountingAccessStore:
    def __init__(self) -> None:
        self.resolve_calls = 0

    def resolve_access_override(self, user_id, now):
        self.resolve_calls += 1
        return AccessOverride()


class CountingAdminStore:
    def __init__(self) -> None:
        self.is_admin_calls = 0

    def is_admin(self, user_id) -> bool:
        self.is_admin_calls += 1
        return True


class CountingBillingRepo:
    def __init__(self) -> None:
        self.calls = 0

    def latest_paid_billing_order(self, user_id):
        self.calls += 1
        return None


def test_access_override_times_authoritative_store_once():
    store = CountingAccessStore()
    request = SimpleNamespace(
        state=SimpleNamespace(current_user=SimpleNamespace(id=USER)),
        app=SimpleNamespace(
            state=SimpleNamespace(multiuser_enabled=True, access_store=store)
        ),
    )
    token = begin_request_timings()
    try:
        resolve_access_override(request)
        resolve_access_override(request)
        snap = snapshot_request_timings()
    finally:
        reset_request_timings(token)
    assert store.resolve_calls == 1
    assert snap["access_override"][1] == 1


def test_access_override_empty_path_does_not_time():
    request = SimpleNamespace(
        state=SimpleNamespace(current_user=None),
        app=SimpleNamespace(state=SimpleNamespace(multiuser_enabled=True, access_store=None)),
    )
    token = begin_request_timings()
    try:
        resolve_access_override(request)
        snap = snapshot_request_timings()
    finally:
        reset_request_timings(token)
    assert "access_override" not in snap


def test_claimed_articles_and_backfill_check_time_once(tmp_path):
    _repo, engine = _seeded_engine(tmp_path)
    token = begin_request_timings()
    try:
        first = engine.claimed_articles()
        snap = snapshot_request_timings()
        assert snap["free_articles_backfill_check"][1] == 1
        assert snap["claimed_articles"][1] == 1
        assert engine.claimed_articles() == first
        snap = snapshot_request_timings()
        assert snap["free_articles_backfill_check"][1] == 1
        assert snap["claimed_articles"][1] == 1
    finally:
        reset_request_timings(token)


def test_settings_frequency_owned_by_engine(tmp_path):
    _repo, engine = _seeded_engine(tmp_path)
    token = begin_request_timings()
    try:
        engine.get_notification_frequency()
        snap = snapshot_request_timings()
    finally:
        reset_request_timings(token)
    assert snap["settings_frequency"][1] == 1


def test_billing_status_times_actual_lookup():
    repo = CountingBillingRepo()
    engine = SimpleNamespace(repo=repo, user_id=USER)
    request = SimpleNamespace(
        state=SimpleNamespace(current_user=SimpleNamespace(id=USER)),
        app=SimpleNamespace(state=SimpleNamespace(article_entitlements_enabled=True)),
    )
    token = begin_request_timings()
    try:
        assert subscription_status(request, engine) is None
        snap = snapshot_request_timings()
    finally:
        reset_request_timings(token)
    assert repo.calls == 1
    assert snap["billing_status"][1] == 1


def test_billing_status_dormant_does_not_time():
    repo = CountingBillingRepo()
    engine = SimpleNamespace(repo=repo, user_id=USER)
    request = SimpleNamespace(
        state=SimpleNamespace(current_user=SimpleNamespace(id=USER)),
        app=SimpleNamespace(state=SimpleNamespace(article_entitlements_enabled=False)),
    )
    token = begin_request_timings()
    try:
        assert subscription_status(request, engine) is None
        snap = snapshot_request_timings()
    finally:
        reset_request_timings(token)
    assert repo.calls == 0
    assert "billing_status" not in snap


def test_admin_hint_cache_hit_does_not_time_again():
    store = CountingAdminStore()
    cache = AdminHintCache()
    request = SimpleNamespace(
        state=SimpleNamespace(current_user=SimpleNamespace(id=USER)),
        app=SimpleNamespace(
            state=SimpleNamespace(
                admin_enabled=True,
                multiuser_enabled=True,
                access_store=store,
                admin_hint_cache=cache,
            )
        ),
    )
    token = begin_request_timings()
    try:
        assert admin_hint(request) is True
        assert snapshot_request_timings()["admin_hint"][1] == 1
        assert store.is_admin_calls == 1
        assert admin_hint(request) is True
        assert snapshot_request_timings()["admin_hint"][1] == 1
        assert store.is_admin_calls == 1
    finally:
        reset_request_timings(token)

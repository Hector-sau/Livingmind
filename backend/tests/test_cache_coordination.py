"""T4: Redis shortens races and speeds up the cooldown check, and nothing depends on it.

Redis tests run only when LIVINGMIND_TEST_REDIS_URL points at a disposable server:
    LIVINGMIND_TEST_REDIS_URL=redis://127.0.0.1:6379/15 pytest
Without it the suite still runs: every cache call degrades to the database path.
"""

from __future__ import annotations

import os

import pytest

from app import config
from app.api.errors import ApiError
from app.cache import Cooldown, SpaceLock, reset_client
from app.cache.client import available, redis_client
from app.contracts import RequestContext
from app.services.rest_service import RestService
from tests.conftest import FakeClock

TEST_REDIS_URL = os.getenv("LIVINGMIND_TEST_REDIS_URL", "").strip()
needs_redis = pytest.mark.skipif(not TEST_REDIS_URL, reason="LIVINGMIND_TEST_REDIS_URL is not set")


def _ctx(person: str = "person-lin") -> RequestContext:
    return RequestContext(account_id="demo-account", person_id=person, space_id="space-home-bedroom")


@pytest.fixture
def redis_on(monkeypatch):
    monkeypatch.setattr(config, "REDIS_URL", TEST_REDIS_URL)
    reset_client()
    client = redis_client()
    client.flushdb()
    try:
        yield client
    finally:
        client.flushdb()
        reset_client()


# ---- without Redis: everything still works, nothing pretends otherwise ----


def test_without_redis_the_lock_is_a_no_op_and_the_flow_works(monkeypatch):
    monkeypatch.setattr(config, "REDIS_URL", "")
    reset_client()
    with SpaceLock("space-home-bedroom") as lock:
        assert lock.degraded and not lock.acquired and not lock.blocked
    assert Cooldown(30).remaining("svc-1") is None

    service = RestService(clock=FakeClock())
    plan = service.create_rest_plan(_ctx(), "我想休息")
    assert service.confirm_plan(plan.plan_id, _ctx(), plan.version).service is not None


def test_unreachable_redis_degrades_instead_of_failing(monkeypatch):
    # A configured but dead server must not take the demo down with it.
    monkeypatch.setattr(config, "REDIS_URL", "redis://127.0.0.1:6399/0")
    reset_client()
    assert available() is False
    with SpaceLock("space-home-bedroom") as lock:
        assert lock.degraded and not lock.blocked
    assert Cooldown(30).remaining("svc-1") is None

    service = RestService(clock=FakeClock())
    plan = service.create_rest_plan(_ctx(), "我想休息")
    confirmed = service.confirm_plan(plan.plan_id, _ctx(), plan.version)
    assert confirmed.service is not None and confirmed.device_state.light_brightness == 15
    reset_client()


# ---- with Redis ----


@needs_redis
def test_lock_is_held_by_one_holder_and_released_by_token(redis_on):
    first = SpaceLock("space-home-bedroom")
    with first as held:
        assert held.acquired
        with SpaceLock("space-home-bedroom") as second:
            assert second.blocked and not second.acquired
        # someone else's expired lock is never deleted by us
        redis_on.set(held.key, "another-token")
    assert redis_on.get(held.key) == "another-token"
    redis_on.delete(held.key)
    with SpaceLock("space-home-bedroom") as third:
        assert third.acquired


@needs_redis
def test_lock_has_a_ttl_so_a_crashed_instance_cannot_block_the_space(redis_on):
    with SpaceLock("space-home-bedroom", ttl_s=5) as lock:
        assert 0 < redis_on.ttl(lock.key) <= 5


@needs_redis
def test_a_second_api_instance_is_refused_while_the_space_is_being_driven(redis_on):
    service = RestService(clock=FakeClock())
    plan = service.create_rest_plan(_ctx(), "我想休息")
    outside = SpaceLock("space-home-bedroom")
    with outside:  # stands in for another API instance mid-execution
        assert outside.acquired
        with pytest.raises(ApiError) as error:
            service.confirm_plan(plan.plan_id, _ctx(), plan.version)
        assert error.value.code == "SPACE_BUSY"
    # once released, the same plan still confirms normally
    assert service.confirm_plan(plan.plan_id, _ctx(), plan.version).service is not None


@needs_redis
def test_cooldown_key_expires_and_is_only_a_fast_path(redis_on):
    service = RestService(clock=FakeClock(), event_cooldown_s=30)
    plan = service.create_rest_plan(_ctx(), "我想休息")
    started = service.confirm_plan(plan.plan_id, _ctx(), plan.version).service
    assert service.inject_event("space-home-bedroom", _ctx(), "room_temperature_changed", 30).outcome == "adjusted"

    key = f"livingmind:cooldown:service:{started.service_id}:room_temp"
    assert 0 < redis_on.ttl(key) <= 30
    ignored = service.inject_event("space-home-bedroom", _ctx(), "room_temperature_changed", 30)
    assert ignored.outcome == "ignored" and "冷却" in ignored.reason

    # Deleting the Redis key does not disable the rule: the service row still enforces it.
    redis_on.delete(key)
    still = service.inject_event("space-home-bedroom", _ctx(), "room_temperature_changed", 30)
    assert still.outcome == "ignored" and "冷却" in still.reason

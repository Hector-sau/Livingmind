"""Queries are leased in short transactions and never become retries of device writes."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import threading

import pytest

from app.contracts import RequestContext
from app.db.ownership import ExecutionOwner
from app.memory.repository import InMemoryPreferenceRepository
from app.services.recovery_worker import RecoveryWorker
from app.services.rest_service import RestService
from tests.conftest import ctx
from tests.test_persistence import needs_db

pytestmark = needs_db


@pytest.fixture
def recovery_case(sql_store, clock):
    service = RestService(store=sql_store, clock=clock, preferences=InMemoryPreferenceRepository())
    context = RequestContext(**ctx())
    gateway = service._gateway(context.space_id)
    submit = gateway.submit

    def lose(request):
        submit(request)
        raise TimeoutError("lost after commit")

    gateway.submit = lose
    response = service.control_device(context.space_id, context, "light", 20)
    return service, gateway, response.result.action_id


def test_background_query_resolves_manual_action_without_submit(recovery_case, sql_store, clock):
    service, gateway, action_id = recovery_case
    before = service._devices[ctx()["spaceId"]].read_state()
    gateway.submit = lambda _: pytest.fail("Recovery must never submit a command")
    result = RecoveryWorker(sql_store, lambda _: gateway, clock).run_once()
    assert result == {"checked": 1, "resolved": 1}
    assert sql_store.get_action_execution(action_id).status == "completed"
    assert service._devices[ctx()["spaceId"]].read_state() == before
    assert RecoveryWorker(sql_store, lambda _: gateway, clock).run_once()["checked"] == 0


def test_backoff_and_exhaustion_keep_unknown_and_manual_query_available(recovery_case, sql_store, clock):
    service, gateway, action_id = recovery_case
    query = gateway.query
    gateway.query = lambda _: None
    worker = RecoveryWorker(sql_store, lambda _: gateway, clock, max_attempts=2)
    assert worker.run_once()["checked"] == 1
    assert worker.run_once()["checked"] == 0
    clock.advance(seconds=2)
    assert worker.run_once()["checked"] == 1
    item = sql_store.get_action_execution(action_id)
    assert item.status == "unknown" and item.recovery_exhausted and item.next_check_at is None
    assert worker.run_once()["checked"] == 0
    gateway.query = query
    assert service.reconcile_action(action_id, RequestContext(**ctx())).status == "completed"
    assert not sql_store.get_action_execution(action_id).recovery_exhausted


def test_age_limit_does_not_misreport_failure(recovery_case, sql_store, clock):
    _, gateway, action_id = recovery_case
    clock.advance(seconds=901)
    gateway.query = lambda _: pytest.fail("Exceeded recovery budget")
    assert RecoveryWorker(sql_store, lambda _: gateway, clock).run_once()["checked"] == 0
    item = sql_store.get_action_execution(action_id)
    assert item.status == "unknown" and item.recovery_exhausted


def test_expired_lease_can_be_reclaimed_but_old_worker_cannot_finish(recovery_case, sql_store, clock):
    _, _, action_id = recovery_case
    first = sql_store.claim_action_recovery(clock(), lease_s=2)
    assert sql_store.claim_action_recovery(clock()) is None
    clock.advance(seconds=3)
    second = sql_store.claim_action_recovery(clock())
    assert second[0].action_id == action_id and second[1] != first[1]
    sql_store.finish_action_recovery(action_id, first[1], clock())
    assert sql_store.claim_action_recovery(clock()) is None
    sql_store.finish_action_recovery(action_id, second[1], clock())
    assert sql_store.get_action_execution(action_id).recovery_attempts == 2


def test_two_workers_do_not_query_the_same_live_lease_or_hold_row_lock(recovery_case, sql_store, clock):
    service, gateway, action_id = recovery_case
    entered, release = threading.Event(), threading.Event()
    query = gateway.query
    count = []

    def slow_query(value):
        count.append(value)
        entered.set()
        assert release.wait(5)
        return query(value)

    gateway.query = slow_query
    worker = RecoveryWorker(sql_store, lambda _: gateway, clock)
    with ThreadPoolExecutor() as pool:
        first = pool.submit(worker.run_once)
        try:
            assert entered.wait(5)
            assert worker.run_once()["checked"] == 0
            # This locks the same row; it must complete while HTTP is still waiting.
            from sqlalchemy import select
            from app.db.models import ActionExecutionRow
            from app.db.session import session_scope
            with session_scope() as session:
                row = session.scalar(select(ActionExecutionRow).where(ActionExecutionRow.action_id == action_id)
                                     .with_for_update(nowait=True))
                assert row.status == "unknown"
        finally:
            release.set()
        assert first.result(5)["resolved"] == 1
    assert count == [action_id]


def test_alive_owner_not_reaped_but_dead_owner_is_recovered(sql_store, clock):
    service = RestService(store=sql_store, clock=clock, preferences=InMemoryPreferenceRepository())
    context = RequestContext(**ctx())
    owner = ExecutionOwner().__enter__()
    sql_store.owner_id = owner.owner_id
    gateway = service._gateway(context.space_id)
    original = gateway.submit

    def crash(request):
        original(request)
        raise RuntimeError("process dies before durable callback")

    gateway.submit = crash
    try:
        with pytest.raises(RuntimeError):
            service.control_device(context.space_id, context, "light", 20)
        item = sql_store.unresolved_action_executions()[0]
        worker = RecoveryWorker(sql_store, lambda _: gateway, clock)
        assert worker.run_once()["checked"] == 0
        assert sql_store.get_action_execution(item.action_id).status == "dispatching"
    finally:
        owner.__exit__(None, None, None)
    assert worker.run_once()["resolved"] == 1
    assert sql_store.get_action_execution(item.action_id).status == "completed"


def test_db_failure_prevents_gateway_query(recovery_case, sql_store, clock, monkeypatch):
    _, gateway, _ = recovery_case
    def outage(**_):
        raise OSError("DB unavailable")
    monkeypatch.setattr(sql_store, "startup_reconcile", outage)
    gateway.query = lambda _: pytest.fail("Do not query without durable coordination")
    with pytest.raises(OSError):
        RecoveryWorker(sql_store, lambda _: gateway, clock).run_once()


def test_reset_during_query_does_not_recreate_cleared_records(recovery_case, sql_store, clock):
    service, gateway, action_id = recovery_case
    receipt = gateway.query(action_id)
    def query(_):
        service.reset("demo-account")
        return receipt
    gateway.query = query
    assert RecoveryWorker(sql_store, lambda _: gateway, clock).run_once()["resolved"] == 0
    assert sql_store.get_action_execution(action_id) is None


def test_background_receipt_after_stop_does_not_resume_service(sql_store, clock):
    from tests.test_action_reconciliation import uncertain_action
    service = RestService(store=sql_store, clock=clock, preferences=InMemoryPreferenceRepository())
    context, gateway, plan, response = uncertain_action(service)
    service.stop_service(response.service.service_id, context)
    before = service.device_state(context.account_id, context.space_id)
    assert RecoveryWorker(sql_store, lambda _: gateway, clock).run_once()["resolved"] == 1
    assert sql_store.get_service(response.service.service_id).status == "stopped"
    assert service.device_state(context.account_id, context.space_id) == before

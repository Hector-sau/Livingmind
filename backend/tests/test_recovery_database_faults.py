"""Actual PostgreSQL TCP disconnection at recovery boundaries; real HTTP virtual gateway.

The fault is scoped to this worker's local proxy, not the database server. Hooks only
choose when to cut sockets; SQL methods still execute and raise real driver errors.
This is connection reset/rejection, not a silent network blackhole or production HA.
"""
from dataclasses import dataclass
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest
from sqlalchemy import NullPool, create_engine, select
from sqlalchemy.exc import OperationalError

from app.adapters.http_gateway import HttpDeviceAdapter, HttpDeviceGateway
from app.clock import utc_now
from app.contracts import RequestContext
from app.db.models import ActionExecutionRow, ActivityRow
from app.memory.repository import InMemoryPreferenceRepository
from app.services.recovery_worker import RecoveryWorker
from app.services.rest_service import RestService
from tests.conftest import TEST_DB_URL, ctx
from tests.tcp_fault_proxy import TcpFaultProxy
from tests.test_persistence import needs_db
from tests.test_persistent_gateway import SPACE, TOKEN, gateway_process

pytestmark = needs_db


@dataclass
class FaultCase:
    store: object
    gateway: object
    adapter: object
    link: TcpFaultProxy
    probe: object
    action_id: str
    queries: list
    clock: object

    def snapshot(self):
        # Independent, direct connection: test observation must not heal the worker's link.
        with self.probe.connect() as connection:
            row = connection.execute(select(ActionExecutionRow).where(
                ActionExecutionRow.action_id == self.action_id)).mappings().one()
            activities = connection.execute(select(ActivityRow.payload)).scalars().all()
        evidence = [a for a in activities if a["activity_id"].startswith("reconcile-")]
        return row, evidence


@pytest.fixture
def fault_case(sql_store, gateway_process, clock, monkeypatch):
    from app import config
    from app.db import session as db_session

    clock.now = utc_now()
    context = RequestContext(**ctx())
    service = RestService(store=sql_store, clock=clock, preferences=InMemoryPreferenceRepository())
    adapter = HttpDeviceAdapter(SPACE, gateway_process.url, TOKEN, sql_store.epoch)
    gateway = HttpDeviceGateway(adapter)
    service._devices[SPACE], service._gateways[SPACE] = adapter, gateway
    submit = gateway.submit

    def lost_reply(request):
        submit(request)
        raise TimeoutError("test reply lost after virtual gateway commit")

    gateway.submit = lost_reply
    response = service.control_device(SPACE, context, "light", 20)
    assert response.result.outcome == "unknown" and adapter.read_state().version == 1
    queries = []
    original_query = gateway.query

    def query(action_id):
        queries.append(action_id)
        return original_query(action_id)

    gateway.query = query
    gateway.submit = lambda _: pytest.fail("Recovery must query, never submit commands")
    link = TcpFaultProxy(TEST_DB_URL)
    probe = create_engine(TEST_DB_URL, poolclass=NullPool)
    old_url = config.DATABASE_URL
    db_session.reset_engine()
    # sql_repo owns the outer config lifetime. Restore here before its teardown;
    # monkeypatch teardown may run after sql_repo and leak its SQL URL into later tests.
    config.DATABASE_URL = link.url
    # Exercise production-style pooling, including a cached socket cut by the proxy.
    monkeypatch.setenv("LIVINGMIND_DB_DISABLE_POOL", "0")
    try:
        assert sql_store.get_action_execution(response.result.action_id).status == "unknown"
        yield FaultCase(sql_store, gateway, adapter, link, probe, response.result.action_id, queries, clock)
    finally:
        link.heal()
        db_session.reset_engine()
        config.DATABASE_URL = old_url
        adapter.close()
        probe.dispose()
        link.close()


def worker(case):
    return RecoveryWorker(case.store, lambda _: case.gateway, case.clock, lease_s=30)


def assert_completed_once(case, attempts):
    row, events = case.snapshot()
    assert row["status"] == "completed" and row["recovery_token"] is None
    assert row["payload"]["recovery_attempts"] == attempts
    assert len(events) == 1 and events[0]["action"]["action_id"] == case.action_id
    assert case.adapter.read_state().version == 1  # Original virtual device write only.


def test_database_disconnect_before_claim_does_not_query_gateway(fault_case):
    case = fault_case
    recovery = worker(case)
    case.link.cut()
    with pytest.raises(OperationalError):
        recovery.run_once()
    row, events = case.snapshot()
    assert row["status"] == "unknown" and row["payload"]["recovery_attempts"] == 0
    assert case.queries == [] and events == []
    case.link.heal()
    assert recovery.run_once() == {"checked": 1, "resolved": 1}
    assert_completed_once(case, 1)


def test_database_disconnect_after_receipt_keeps_unknown_until_lease_expires(fault_case):
    case = fault_case
    recovery = worker(case)
    original = case.gateway.query

    def cut_after_query(action_id):
        receipt = original(action_id)
        assert receipt.status == "completed"
        case.link.cut()
        return receipt

    case.gateway.query = cut_after_query
    with pytest.raises(OperationalError):
        recovery.run_once()
    row, events = case.snapshot()
    assert row["status"] == "unknown" and row["recovery_token"] is not None
    assert row["payload"]["recovery_attempts"] == 1 and events == []
    assert case.queries == [case.action_id]
    case.link.heal()
    case.gateway.query = original
    assert recovery.run_once() == {"checked": 0, "resolved": 0}  # Existing lease is not stolen.
    case.clock.advance(seconds=31)  # Advance only the test clock; no production TTL changes.
    assert recovery.run_once() == {"checked": 1, "resolved": 1}
    assert case.queries == [case.action_id, case.action_id]
    assert_completed_once(case, 2)


def test_database_disconnect_after_commit_preserves_terminal_and_single_event(fault_case, monkeypatch):
    case = fault_case
    recovery = worker(case)
    resolve = case.store.resolve_unknown_action

    def cut_after_commit(*args, **kwargs):
        result = resolve(*args, **kwargs)
        # The method has returned from its real SQL transaction, then transport fails.
        assert result.status == "completed"
        case.link.cut()
        return result

    monkeypatch.setattr(case.store, "resolve_unknown_action", cut_after_commit)
    with pytest.raises(OperationalError):
        recovery.run_once()  # Cleanup fails, but the committed result must not be downgraded.
    assert_completed_once(case, 1)
    case.link.heal()
    assert recovery.run_once() == {"checked": 0, "resolved": 0}
    assert case.queries == [case.action_id]
    assert_completed_once(case, 1)


def test_background_process_survives_database_outage_and_recovers_after_heal(fault_case, gateway_process, tmp_path):
    case = fault_case
    case.link.cut()
    log_path = tmp_path / "recovery-worker.log"
    env = {**os.environ, "LIVINGMIND_DATABASE_URL": case.link.url,
           "LIVINGMIND_GATEWAY_URL": gateway_process.url, "LIVINGMIND_GATEWAY_TOKEN": TOKEN,
           "LIVINGMIND_REDIS_URL": "", "LIVINGMIND_DB_DISABLE_POOL": "0"}
    with log_path.open("w") as output:
        process = subprocess.Popen([sys.executable, "-m", "app.services.recovery_worker"],
                                   cwd=Path(__file__).resolve().parents[1], env=env,
                                   stdout=output, stderr=subprocess.STDOUT)
        original_pid = process.pid
        try:
            deadline = time.monotonic() + 15
            while "Recovery pass failed (OperationalError)" not in log_path.read_text():
                assert process.poll() is None, log_path.read_text()
                assert time.monotonic() < deadline, "Worker did not observe the real DB outage"
                time.sleep(.05)
            row, events = case.snapshot()
            assert row["status"] == "unknown" and row["payload"]["recovery_attempts"] == 0
            assert events == [] and case.adapter.read_state().version == 1
            case.link.heal()
            deadline = time.monotonic() + 15
            while case.snapshot()[0]["status"] != "completed":
                assert process.poll() is None, log_path.read_text()
                assert time.monotonic() < deadline, "Worker did not resume after link healing"
                time.sleep(.1)
            assert process.pid == original_pid and process.poll() is None
            assert_completed_once(case, 1)
            assert TOKEN not in log_path.read_text() and case.link.url not in log_path.read_text()
        finally:
            case.link.heal()
            process.terminate()
            process.wait(10)

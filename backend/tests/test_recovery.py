"""Startup recovery is explicit and never replays a device action with an unknown outcome."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.session import engine
from app.main import create_app
from app.services.rest_service import RestService, get_rest_service
from tests.conftest import ctx, sql_mode


def test_memory_mode_reports_that_restart_recovery_is_not_available(client):
    if sql_mode():
        pytest.skip("memory-mode assertion")
    status = client.get("/api/system/recovery", params={"accountId": "demo-account"}).json()
    assert status["store"] == "memory"
    assert status["deviceStateReconciled"] is False
    assert "没有跨进程恢复" in status["note"]


def test_postgres_restart_cancels_unknown_running_step_instead_of_replaying(client, clock):
    if not sql_mode():
        pytest.skip("requires disposable PostgreSQL")
    plan = client.post("/api/plans/rest", json={"context": ctx(), "utterance": "我想休息"}).json()
    client.post(
        f"/api/plans/{plan['planId']}/confirm",
        json={"context": ctx(), "planVersion": plan["version"]},
    )
    with engine().begin() as connection:
        connection.execute(
            text(
                "UPDATE scheduled_steps SET status='running', "
                "payload=jsonb_set(payload, '{status}', '\"running\"') "
                "WHERE step_id=(SELECT step_id FROM scheduled_steps ORDER BY ordinal LIMIT 1)"
            )
        )
        connection.execute(
            text("INSERT INTO service_flags(service_id, flag) SELECT service_id, 'replanning' FROM services LIMIT 1")
        )
        connection.execute(
            text(
                "UPDATE action_executions SET status='accepted', "
                "payload=jsonb_set(payload, '{status}', '\"accepted\"') "
                "WHERE action_id=(SELECT action_id FROM action_executions ORDER BY action_id LIMIT 1)"
            )
        )

    recovered = RestService(clock=clock)
    app = create_app()
    app.dependency_overrides[get_rest_service] = lambda: recovered
    status = TestClient(app).get("/api/system/recovery", params={"accountId": "demo-account"}).json()
    assert status["store"] == "postgresql"
    assert status["activeServices"] == 1
    assert status["cancelledUnknownSteps"] == 1
    assert status["clearedInflightFlags"] == 1
    assert status["unknownActions"] == 1
    assert status["deviceStateReconciled"] is False

    with engine().connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM scheduled_steps WHERE status='running'")).scalar_one() == 0
        assert connection.execute(text("SELECT count(*) FROM service_flags")).scalar_one() == 0
        assert connection.execute(text("SELECT count(*) FROM action_executions WHERE status='unknown'")).scalar_one() == 1

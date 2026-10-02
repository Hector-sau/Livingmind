"""Request IDs travel through synchronous API work into event envelopes."""

import json
import logging

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.models import OutboxEventRow
from app.db.session import session_scope
from app.events.envelope import event
from app.main import create_app
from tests.test_persistence import needs_db


def test_request_id_is_returned_logged_and_carried_into_sync_route():
    app = create_app()

    @app.get("/test-correlation")
    def correlation():
        envelope = event("plan.created", occurred_at="2026-10-02T00:00:00Z",
                         space_id="space-home-bedroom", aggregate_id="plan-1")
        return {"correlationId": envelope.correlation_id}

    records = []

    class Capture(logging.Handler):
        def emit(self, record):
            records.append(record)

    logger = logging.getLogger("livingmind.http")
    assert not logger.disabled, "in-process Alembic migrations must not disable HTTP logging"
    capture = Capture()
    logger.addHandler(capture)
    try:
        with TestClient(app) as client:
            response = client.get("/test-correlation", headers={"X-Request-ID": "interview-probe-1"})
    finally:
        logger.removeHandler(capture)
    assert len(records) == 1
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "interview-probe-1"
    assert response.json()["correlationId"] == "interview-probe-1"
    record = json.loads(records[0].getMessage())
    assert record["requestId"] == "interview-probe-1"
    assert record["durationMs"] >= 0 and record["status"] == 200
    assert "user text" not in json.dumps(record)


@needs_db
def test_real_plan_event_uses_http_request_id(client):
    body = {"context": {"accountId": "demo-account", "personId": "person-lin", "spaceId": "space-home-bedroom"},
            "utterance": "我想休息", "mode": "rule"}
    response = client.post("/api/plans/rest", json=body, headers={"X-Request-ID": "plan-trace-42"})
    assert response.status_code == 200
    with session_scope() as session:
        rows = session.scalars(select(OutboxEventRow).where(OutboxEventRow.event_type == "plan.created")).all()
    assert any(row.payload["correlationId"] == "plan-trace-42" for row in rows)


def test_plan_and_action_logs_join_http_requests_without_private_text(client):
    records = []

    class Capture(logging.Handler):
        def emit(self, record):
            records.append(json.loads(record.getMessage()))

    logger = logging.getLogger("livingmind.events")
    assert not logger.disabled
    capture = Capture()
    logger.addHandler(capture)
    context = {"accountId": "demo-account", "personId": "person-lin", "spaceId": "space-home-bedroom"}
    try:
        response = client.post("/api/assistant/messages", json={
            "context": context, "text": "我想休息 private-test-marker", "mode": "rule",
        }, headers={"X-Request-ID": "plan-request"})
        assert response.status_code == 200
        plan = response.json()["plan"]
        confirmed = client.post(f"/api/plans/{plan['planId']}/confirm", json={
            "context": context, "planVersion": plan["version"],
        }, headers={"X-Request-ID": "confirm-request"})
        assert confirmed.status_code == 200
    finally:
        logger.removeHandler(capture)

    stages = [row for row in records if row["event"] == "agent.stage"]
    assert {row["agent"] for row in stages} >= {"orchestrator", "memory", "experience", "harness"}
    assert all(row["requestId"] == "plan-request" and row["durationMs"] >= 0 for row in stages)
    ready = next(row for row in records if row["event"] == "plan.ready")
    assert ready["planId"] == plan["planId"] and ready["requestId"] == "plan-request"
    finished = [row for row in records if row["event"] == "action.finished"]
    assert len(finished) == 3
    assert all(row["requestId"] == "confirm-request" and row["planId"] == plan["planId"]
               and row["serviceId"] == confirmed.json()["service"]["serviceId"] for row in finished)
    assert {row["actionId"] for row in finished} == set(ready["actionIds"])
    assert len([row for row in records if row["event"] == "gateway.readback"]) == 3
    assert "private-test-marker" not in json.dumps(records)

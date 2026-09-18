"""Acceptance checks for step 4 (numbers match docs/acceptance.md)."""

from app.contracts import DeviceAction
from app.harness.executor import Executor
from tests.conftest import ctx

SPACE = "space-home-bedroom"


def devices(client):
    res = client.get(f"/api/spaces/{SPACE}/devices", params={"accountId": "demo-account"})
    assert res.status_code == 200
    return res.json()


def make_plan(client, person="person-lin"):
    res = client.post("/api/plans/rest", json={"context": ctx(person), "utterance": "我想休息"})
    assert res.status_code == 200, res.text
    return res.json()


def confirm(client, plan, person="person-lin"):
    return client.post(
        f"/api/plans/{plan['planId']}/confirm",
        json={"context": ctx(person), "planVersion": plan["version"]},
    )


# 1
def test_creating_plan_does_not_change_devices(client):
    before = devices(client)
    plan = make_plan(client)
    assert plan["status"] == "proposed" and plan["source"] == "rule"
    assert devices(client) == before


# 2
def test_confirm_changes_backend_state_and_reads_back(client):
    plan = make_plan(client)
    res = confirm(client, plan)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["service"]["status"] == "active"
    assert all(r["outcome"] == "succeeded" for r in body["results"])
    state = devices(client)
    assert state["source"] == "virtual_device"
    assert (state["lightBrightness"], state["acTargetTempC"], state["curtainOpenPercent"]) == (15, 25.0, 0)
    assert state["version"] == 3


# 3
def test_persons_get_different_plans(client):
    a = make_plan(client, "person-lin")
    b = make_plan(client, "person-chen")
    assert [x["value"] for x in a["actions"]] != [x["value"] for x in b["actions"]]


# 4
def test_repeat_confirm_does_not_execute_again(client):
    plan = make_plan(client)
    first = confirm(client, plan).json()
    second = confirm(client, plan)
    assert second.status_code == 200
    assert second.json()["repeated"] is True
    assert devices(client)["version"] == first["deviceState"]["version"]


def test_only_one_active_service_per_space(client):
    confirm(client, make_plan(client))
    other = make_plan(client, "person-chen")
    res = confirm(client, other, "person-chen")
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "SERVICE_ALREADY_ACTIVE"


# 5
def test_stop_invalidates_older_plans_and_keeps_devices(client):
    pending = make_plan(client)
    started = confirm(client, make_plan(client)).json()
    version_after_start = devices(client)["version"]

    res = client.post(f"/api/services/{started['service']['serviceId']}/stop", json={"context": ctx()})
    assert res.status_code == 200
    assert res.json()["service"]["status"] == "stopped"
    assert devices(client)["version"] == version_after_start  # no automatic restore

    # the old, never-confirmed plan cannot restart the service
    res = confirm(client, pending)
    assert res.status_code == 409 and res.json()["error"]["code"] == "PLAN_INVALIDATED"
    # re-confirming the executed plan does not restart it either
    again = confirm(client, {"planId": started["plan"]["planId"], "version": 1}).json()
    assert again["repeated"] is True and again["service"]["status"] == "stopped"
    assert devices(client)["version"] == version_after_start

    # stopping twice is rejected
    res = client.post(f"/api/services/{started['service']['serviceId']}/stop", json={"context": ctx()})
    assert res.json()["error"]["code"] == "SERVICE_NOT_ACTIVE"


def test_executor_checks_guard_before_every_action(service):
    """A stop landing mid-plan prevents the remaining actions."""
    adapter = service._devices[SPACE]
    actions = [
        DeviceAction(action_id="a1", device="light", command="set_brightness", value=10, label="l"),
        DeviceAction(action_id="a2", device="ac", command="set_target_temperature", value=23, label="t"),
    ]
    calls = {"n": 0}

    def guard():
        calls["n"] += 1
        return None if calls["n"] == 1 else "服务已停止"

    results = Executor(adapter).run(actions, guard, lambda a, r: None)
    assert [r.outcome for r in results] == ["succeeded", "skipped"]
    assert adapter.read_state().ac_target_temp_c == 26.0


def test_executor_reports_readback_errors_as_action_failures(service, monkeypatch):
    adapter = service._devices[SPACE]
    action = DeviceAction(action_id="a1", device="light", command="set_brightness", value=10, label="l")

    def fail_read(_device):
        raise TimeoutError("device read timeout")

    monkeypatch.setattr(adapter, "read_value", fail_read)
    results = Executor(adapter).run([action], lambda: None, lambda a, r: None)
    assert results[0].outcome == "failed"
    assert results[0].observed_value is None
    assert results[0].reason == "设备写入后回读失败：device read timeout"


# 6
def test_illegal_person_is_rejected(client):
    res = client.post("/api/plans/rest", json={"context": ctx("intruder"), "utterance": "我想休息"})
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "FORBIDDEN_CONTEXT"


def test_illegal_space_and_account_are_rejected(client):
    res = client.post("/api/plans/rest", json={"context": ctx(space="space-other"), "utterance": "我想休息"})
    assert res.json()["error"]["code"] == "FORBIDDEN_CONTEXT"
    res = client.get("/api/bootstrap", params={"accountId": "someone"})
    assert res.status_code == 403


def test_plan_of_another_person_cannot_be_confirmed(client):
    plan = make_plan(client, "person-lin")
    res = confirm(client, plan, "person-chen")
    assert res.status_code == 403


def test_expired_plan_is_rejected(client, clock):
    plan = make_plan(client)
    clock.advance(minutes=11)
    res = confirm(client, plan)
    assert res.status_code == 409 and res.json()["error"]["code"] == "PLAN_EXPIRED"
    assert devices(client)["version"] == 0


def test_version_mismatch_is_rejected(client):
    plan = make_plan(client)
    res = confirm(client, {**plan, "version": 2})
    assert res.json()["error"]["code"] == "PLAN_VERSION_MISMATCH"


def test_out_of_range_and_unlisted_actions_are_rejected(service):
    adapter = service._devices[SPACE]
    bad = [
        DeviceAction(action_id="b1", device="ac", command="set_target_temperature", value=5, label="too cold"),
        DeviceAction(action_id="b2", device="light", command="set_brightness", value=150, label="too bright"),
        DeviceAction(action_id="b3", device="light", command="set_brightness", value=10.5, label="not int"),
    ]
    results = Executor(adapter).run(bad, lambda: None, lambda a, r: None)
    assert [r.outcome for r in results] == ["rejected"] * 3
    assert adapter.read_state().version == 0


def test_bad_request_body_uses_unified_error(client):
    res = client.post("/api/plans/rest", json={"context": ctx(), "utterance": ""})
    assert res.status_code == 422 and res.json()["error"]["code"] == "VALIDATION_ERROR"


def test_activity_records_what_actually_happened(client):
    plan = make_plan(client)
    confirm(client, plan)
    items = client.get(f"/api/spaces/{SPACE}/activity", params={"accountId": "demo-account"}).json()["items"]
    kinds = [i["kind"] for i in items]
    assert kinds[0] == "action_executed"  # newest first
    assert kinds.count("action_executed") == 3
    assert "plan_confirmed" in kinds and "plan_created" in kinds
    assert all(i["source"] != "frontend_mock" for i in items)


def test_reset_restores_initial_state(client):
    confirm(client, make_plan(client))
    body = client.post("/api/demo/reset", params={"accountId": "demo-account"}).json()
    assert body["activeService"] is None
    assert body["deviceState"]["lightBrightness"] == 80 and body["deviceState"]["version"] == 0
    items = client.get(f"/api/spaces/{SPACE}/activity", params={"accountId": "demo-account"}).json()["items"]
    assert [i["kind"] for i in items] == ["demo_reset"]


def test_unexpected_errors_use_unified_format(service, monkeypatch):
    from fastapi.testclient import TestClient

    from app.main import create_app
    from app.services.rest_service import get_rest_service

    def boom(*a, **kw):
        raise RuntimeError("secret internal detail")

    monkeypatch.setattr(service, "bootstrap", boom)
    app = create_app()
    app.dependency_overrides[get_rest_service] = lambda: service
    res = TestClient(app, raise_server_exceptions=False).get("/api/bootstrap", params={"accountId": "demo-account"})
    assert res.status_code == 500
    body = res.json()
    assert body["error"]["code"] == "INTERNAL_ERROR"
    assert "secret internal detail" not in res.text

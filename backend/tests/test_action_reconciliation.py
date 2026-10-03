from dataclasses import replace

import pytest

from app.adapters.protocol import DeviceCommandReceipt
from app.contracts import RequestContext
from tests.conftest import ctx


def uncertain_action(service):
    context = RequestContext(**ctx())
    gateway = service._gateway(context.space_id)
    original = gateway.submit

    def lost_reply(request):
        receipt = original(request)  # write and persist receipt, then lose the first reply
        if request.device_type == "light":
            raise TimeoutError("lost reply")
        return receipt

    gateway.submit = lost_reply
    plan = service.create_rest_plan(context, "我想休息")
    response = service.confirm_plan(plan.plan_id, context, plan.version)
    assert [item.outcome for item in response.results] == ["unknown", "succeeded", "succeeded"]
    return context, gateway, plan, response


def test_reconcile_lost_reply_updates_ledger_and_plan_without_a_second_write(service, client):
    context, gateway, plan, response = uncertain_action(service)
    before = service.device_state(context.account_id, context.space_id)
    action_id = plan.actions[0].action_id
    resolved = client.post(f"/api/actions/{action_id}/reconcile", json={"context": ctx()})
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "completed" and resolved.json()["attemptCount"] == 1
    again = client.post(f"/api/actions/{action_id}/reconcile", json={"context": ctx()})
    assert again.json() == resolved.json()
    records = service.activity(context.account_id, context.space_id, 100)
    assert len([r for r in records if r.activity_id.startswith("reconcile-")]) == 1
    repeated = service.confirm_plan(plan.plan_id, context, plan.version)
    assert repeated.results[0].outcome == "succeeded"
    assert repeated.results[1].outcome == "succeeded"
    assert service.device_state(context.account_id, context.space_id) == before


def test_late_unknown_callback_does_not_duplicate_or_replace_a_reconciled_result(service):
    context, _, plan, response = uncertain_action(service)
    late = response.results[0]
    service.reconcile_action(late.action_id, context)
    service._store.append_result(plan.plan_id, late)
    results = service._store.get_plan(plan.plan_id).results
    assert len(results) == 3
    assert results[0].outcome == "succeeded"


@pytest.mark.parametrize("kind", ["missing", "wrong_id", "accepted", "timeout", "no_time", "old_time"])
def test_insufficient_receipt_evidence_stays_unknown(service, kind):
    context, gateway, plan, response = uncertain_action(service)
    action_id = plan.actions[0].action_id
    receipt = gateway.query(action_id)
    if kind == "timeout":
        def query(_):
            raise TimeoutError()
        gateway.query = query
    else:
        from datetime import timedelta
        value = {"missing": None, "wrong_id": replace(receipt, action_id="other"),
                 "accepted": replace(receipt, status="accepted"), "no_time": replace(receipt, observed_at=None),
                 "old_time": replace(receipt, observed_at=service._clock() - timedelta(seconds=1))}[kind]
        gateway.query = lambda _: value
    assert service.reconcile_action(action_id, context).status == "unknown"


def test_reconciliation_cannot_read_another_persons_action(service, client):
    _, _, plan, _ = uncertain_action(service)
    response = client.post(f"/api/actions/{plan.actions[0].action_id}/reconcile", json={"context": ctx("person-chen")})
    assert response.status_code == 403


def test_receipt_after_stop_does_not_restart_service(service):
    context, gateway, plan, response = uncertain_action(service)
    service.stop_service(response.service.service_id, context)
    before = service.device_state(context.account_id, context.space_id)
    assert service.reconcile_action(plan.actions[0].action_id, context).status == "completed"
    assert service._store.get_service(response.service.service_id).status == "stopped"
    assert service.device_state(context.account_id, context.space_id) == before


@pytest.mark.parametrize("phase", ["submit", "query"])
def test_executor_never_uses_a_receipt_from_a_different_action(service, phase):
    context = RequestContext(**ctx())
    gateway = service._gateway(context.space_id)
    original = gateway.submit

    def submit(request):
        receipt = original(request)
        return replace(receipt, action_id="wrong-action") if phase == "submit" else replace(receipt, status="accepted")

    query = gateway.query
    gateway.submit = submit
    gateway.query = lambda action_id: replace(query(action_id), action_id="wrong-action")
    plan = service.create_rest_plan(context, "我想休息")
    response = service.confirm_plan(plan.plan_id, context, plan.version)
    assert all(result.outcome == "unknown" for result in response.results)


@pytest.mark.parametrize("status,value,expected", [("completed", 99, "failed"), ("failed", None, "failed"), ("rejected", None, "rejected")])
def test_reconciliation_preserves_negative_terminal_results(service, status, value, expected):
    context, gateway, plan, _ = uncertain_action(service)
    action_id = plan.actions[0].action_id
    receipt = gateway.query(action_id)
    gateway.query = lambda _: replace(receipt, status=status, observed_value=value)
    assert service.reconcile_action(action_id, context).status == expected
    # Later contradictory data must not overwrite an already terminal decision.
    gateway.query = lambda _: receipt
    assert service.reconcile_action(action_id, context).status == expected

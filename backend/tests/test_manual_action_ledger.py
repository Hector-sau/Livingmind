"""All user entry points have durable, person-scoped evidence, including lost replies."""
import pytest

from app.contracts import RequestContext
from tests.conftest import ctx


def lose_reply(service):
    gateway = service._gateway("space-home-bedroom")
    original = gateway.submit

    def submit(request):
        result = original(request)
        raise TimeoutError("response lost after commit")

    gateway.submit = submit
    return gateway


def test_manual_action_record_exists_before_gateway_submit(service):
    context = RequestContext(**ctx())
    gateway = service._gateway(context.space_id)
    original = gateway.submit

    def submit(request):
        item = service._store.get_action_execution(request.action_id)
        assert item.status == "dispatching" and item.attempt_count == 1
        assert item.source == "manual" and item.person_id == context.person_id
        assert item.account_id == context.account_id and item.plan_id is None and item.grant_id is None
        return original(request)

    gateway.submit = submit
    result = service.control_device(context.space_id, context, "light", 20)
    assert service._store.get_action_execution(result.result.action_id).status == "completed"


@pytest.mark.parametrize("source", ["manual", "undo"])
def test_control_and_undo_lost_replies_can_be_reconciled_without_writing(service, client, source):
    context = RequestContext(**ctx())
    first = service.control_device(context.space_id, context, "light", 20)
    lose_reply(service)
    response = (service.undo_device_control(first.undo.undo_id, context) if source == "undo"
                else service.control_device(context.space_id, context, "light", 25))
    action_id = response.result.action_id
    assert response.result.outcome == "unknown"
    before = service.device_state(context.account_id, context.space_id)
    item = service._store.get_action_execution(action_id)
    assert item.source == source and item.status == "unknown"
    other = client.post(f"/api/actions/{action_id}/reconcile", json={"context": ctx("person-chen")})
    assert other.status_code == 403
    assert client.get("/api/actions", params=ctx("person-chen")).json() == []
    result = client.post(f"/api/actions/{action_id}/reconcile", json={"context": ctx()})
    assert result.status_code == 200 and result.json()["status"] == "completed"
    service.reconcile_action(action_id, context)
    assert service.device_state(context.account_id, context.space_id) == before
    assert len([a for a in service.activity(context.account_id, context.space_id, 50)
                if a.activity_id.startswith("reconcile-")]) == 1
    history = client.get("/api/actions", params=ctx()).json()
    assert any(a["actionId"] == action_id and a["status"] == "completed" for a in history)


def test_device_snapshot_failure_preserves_action_result_in_response(service, client):
    context = RequestContext(**ctx())
    adapter = service._devices[context.space_id]
    original = service._gateway(context.space_id).submit

    def submit(request):
        result = original(request)
        def offline():
            raise OSError("offline after commit")
        adapter.read_state = offline
        return result

    service._gateway(context.space_id).submit = submit
    response = client.post(f"/api/spaces/{context.space_id}/devices/control",
                           json={"context": ctx(), "device": "light", "value": 25})
    assert response.status_code == 200
    assert response.json()["result"]["outcome"] == "succeeded"
    assert response.json()["deviceState"] is None and response.json()["warning"]


def test_terminal_ledger_rejects_late_unknown_callback(service):
    context = RequestContext(**ctx())
    lose_reply(service)
    response = service.control_device(context.space_id, context, "light", 25)
    old = service._store.get_action_execution(response.result.action_id)
    service.reconcile_action(old.action_id, context)
    service._store.save_action_execution(old)
    assert service._store.get_action_execution(old.action_id).status == "completed"


def test_failed_new_control_does_not_leave_an_old_undo_offer(service):
    context = RequestContext(**ctx())
    first = service.control_device(context.space_id, context, "light", 20)
    lose_reply(service)
    service.control_device(context.space_id, context, "light", 25)
    from app.api.errors import ApiError
    with pytest.raises(ApiError) as exc:
        service.undo_device_control(first.undo.undo_id, context)
    assert exc.value.code == "UNDO_EXPIRED"

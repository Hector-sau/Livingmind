"""Execution authority: confirmation creates bounded grants and durable commands."""

import threading
from datetime import timedelta

import pytest

from app.adapters.gateway import AdapterDeviceGateway
from app.adapters.protocol import DeviceCommandReceipt, DeviceCommandRequest
from app.adapters.virtual.devices import VirtualDeviceAdapter
from app.contracts import Capability, DeviceAction, ExecutionGrant, RequestContext
from app.demo import seed
from app.harness.executor import Executor
from tests.conftest import FakeClock, ctx

SPACE = "space-home-bedroom"


def _ctx():
    return RequestContext(**ctx())


def test_confirmation_creates_policy_grant_and_completed_action_ledger(service):
    plan = service.create_rest_plan(_ctx(), "我想休息")
    response = service.confirm_plan(plan.plan_id, _ctx(), plan.version)

    decision = response.policy_decision
    grant = response.execution_grant
    assert decision is not None and decision.decision == "require_confirmation"
    assert decision.plan_hash == grant.plan_hash
    assert grant is not None and grant.status == "active"
    assert grant.account_id == "demo-account" and grant.service_id == response.service.service_id
    assert grant.service_epoch == service._store.epoch(SPACE)

    executions = [service._store.get_action_execution(action.action_id) for action in plan.actions]
    assert all(item is not None and item.status == "completed" for item in executions)
    assert all(item.grant_id == grant.grant_id and item.attempt_count == 1 for item in executions)


def test_direct_command_grant_is_limited_to_the_confirmed_value(service):
    reply = service.handle_message(_ctx(), "把空调调到24度")
    plan = reply.plan
    response = service.confirm_plan(plan.plan_id, _ctx(), plan.version)

    assert response.service is None
    assert len(response.execution_grant.capabilities) == 1
    capability = response.execution_grant.capabilities[0]
    assert (capability.device, capability.command) == ("ac", "set_target_temperature")
    assert capability.min == capability.max == 24


def test_stop_revokes_grant_and_gateway_rejects_stale_epoch(service):
    plan = service.create_rest_plan(_ctx(), "我想休息")
    started = service.confirm_plan(plan.plan_id, _ctx(), plan.version)
    grant = started.execution_grant
    gateway = service._gateway(SPACE)
    before = service._devices[SPACE].read_state().version

    service.stop_service(started.service.service_id, _ctx())
    stored = service._store.get_grant(grant.grant_id)
    assert stored.status == "revoked" and stored.revoked_at is not None

    receipt = gateway.submit(
        DeviceCommandRequest(
            action_id="late-action",
            service_id=started.service.service_id,
            service_epoch=grant.service_epoch,
            device_id=f"{SPACE}:light",
            device_type="light",
            command="set_brightness",
            value=99,
            requested_at=service._clock(),
        )
    )
    assert receipt.status == "rejected" and "stale service epoch" in receipt.detail
    assert service._devices[SPACE].read_state().version == before


def test_gateway_action_id_is_idempotent():
    clock = FakeClock()
    adapter = VirtualDeviceAdapter(SPACE, seed.INITIAL_DEVICE_STATE, clock)
    gateway = AdapterDeviceGateway(adapter)
    request = DeviceCommandRequest(
        action_id="same-action",
        service_id=None,
        service_epoch=0,
        device_id=f"{SPACE}:light",
        device_type="light",
        command="set_brightness",
        value=20,
        requested_at=clock(),
    )
    first = gateway.submit(request)
    second = gateway.submit(request)
    assert first == second and first.status == "completed"
    assert adapter.read_state().version == 1


def test_concurrent_retry_reserves_action_id_before_device_write():
    clock = FakeClock()

    class BlockingAdapter(VirtualDeviceAdapter):
        def __init__(self):
            super().__init__(SPACE, seed.INITIAL_DEVICE_STATE, clock)
            self.started = threading.Event()
            self.release = threading.Event()

        def _before_write(self, device, command, value):
            self.started.set()
            assert self.release.wait(timeout=5)

    adapter = BlockingAdapter()
    gateway = AdapterDeviceGateway(adapter)
    request = DeviceCommandRequest(
        action_id="concurrent-action",
        service_id=None,
        service_epoch=0,
        device_id=f"{SPACE}:light",
        device_type="light",
        command="set_brightness",
        value=20,
        requested_at=clock(),
    )
    first = {}
    worker = threading.Thread(target=lambda: first.setdefault("receipt", gateway.submit(request)))
    worker.start()
    assert adapter.started.wait(timeout=5)
    retry = gateway.submit(request)
    assert retry.status == "accepted"
    adapter.release.set()
    worker.join(timeout=5)
    assert first["receipt"].status == "completed"
    assert adapter.read_state().version == 1


def test_same_action_id_with_different_payload_is_rejected():
    clock = FakeClock()
    adapter = VirtualDeviceAdapter(SPACE, seed.INITIAL_DEVICE_STATE, clock)
    gateway = AdapterDeviceGateway(adapter)
    original = DeviceCommandRequest(
        action_id="conflict-action",
        service_id=None,
        service_epoch=0,
        device_id=f"{SPACE}:light",
        device_type="light",
        command="set_brightness",
        value=20,
        requested_at=clock(),
    )
    gateway.submit(original)
    conflict = original.__class__(**{**original.__dict__, "value": 80})
    receipt = gateway.submit(conflict)
    assert receipt.status == "rejected" and "actionId" in receipt.detail
    assert adapter.read_value("light") == 20


def test_grant_scope_can_be_narrower_than_platform_policy():
    clock = FakeClock()
    adapter = VirtualDeviceAdapter(SPACE, seed.INITIAL_DEVICE_STATE, clock)
    now = clock()
    grant = ExecutionGrant(
        grant_id="g1",
        policy_decision_id="d1",
        account_id="demo-account",
        person_id="person-lin",
        space_id=SPACE,
        plan_id="p1",
        plan_version=1,
        plan_hash="hash",
        service_id=None,
        service_epoch=0,
        capabilities=[Capability(device="light", command="set_brightness", min=0, max=20, integer=True)],
        max_adjustments=0,
        status="active",
        created_at=now,
        valid_until=now + timedelta(minutes=10),
    )
    action = DeviceAction(
        action_id="a1", device="light", command="set_brightness", value=50, label="调亮灯光"
    )
    results = Executor(adapter, clock=clock).run(
        [action], lambda: None, lambda _a, _r: None, grant=grant, plan_id="p1", service_epoch=0
    )
    assert results[0].outcome == "rejected" and "授权范围" in results[0].reason
    assert adapter.read_state().version == 0


class AcceptedForeverGateway:
    def list_devices(self, space_id):
        return []

    def advance_fence(self, space_id, service_epoch):
        return None

    def submit(self, request):
        return DeviceCommandReceipt(request.action_id, "accepted", None, None)

    def query(self, action_id):
        return DeviceCommandReceipt(action_id, "accepted", None, None)


def test_accepted_without_terminal_receipt_is_unknown_and_recorded():
    clock = FakeClock()
    adapter = VirtualDeviceAdapter(SPACE, seed.INITIAL_DEVICE_STATE, clock)
    now = clock()
    grant = ExecutionGrant(
        grant_id="g2",
        policy_decision_id="d2",
        account_id="demo-account",
        person_id="person-lin",
        space_id=SPACE,
        plan_id="p2",
        plan_version=1,
        plan_hash="hash",
        service_id=None,
        service_epoch=0,
        capabilities=[Capability(device="light", command="set_brightness", min=0, max=100, integer=True)],
        max_adjustments=0,
        status="active",
        created_at=now,
        valid_until=now + timedelta(minutes=10),
    )
    action = DeviceAction(
        action_id="a2", device="light", command="set_brightness", value=20, label="调暗灯光"
    )
    transitions = []
    result = Executor(adapter, gateway=AcceptedForeverGateway(), clock=clock).run(
        [action],
        lambda: None,
        lambda _a, _r: None,
        grant=grant,
        plan_id="p2",
        service_epoch=0,
        on_execution=transitions.append,
    )[0]
    assert result.outcome == "unknown"
    assert [item.status for item in transitions] == ["pending", "dispatching", "accepted", "unknown"]
    assert adapter.read_state().version == 0


@pytest.mark.parametrize("lost_at,expected_writes", [("before_submit", 0), ("after_write", 1), ("query", 1)])
def test_lost_gateway_reply_is_unknown_and_repeat_confirmation_never_resends(service, lost_at, expected_writes):
    """A timeout cannot tell us whether the device applied the command."""
    adapter = service._devices[SPACE]

    class LostReplyGateway(AdapterDeviceGateway):
        def submit(self, request):
            if lost_at == "before_submit":
                raise ConnectionError("connection dropped before acknowledgement")
            receipt = super().submit(request)
            if lost_at == "after_write":
                raise TimeoutError("device wrote, response was lost")
            return DeviceCommandReceipt(request.action_id, "accepted", None, None)

        def query(self, action_id):
            raise TimeoutError("receipt query response was lost")

    service._gateways[SPACE] = LostReplyGateway(adapter)
    plan = service.handle_message(_ctx(), "把空调调到24度").plan
    first = service.confirm_plan(plan.plan_id, _ctx(), plan.version)
    assert first.results[0].outcome == "unknown"
    action = service._store.get_action_execution(plan.actions[0].action_id)
    assert action.status == "unknown" and action.attempt_count == 1
    assert action.error_kind == ("offline" if lost_at == "before_submit" else "timeout")
    assert adapter.read_state().version == expected_writes

    repeated = service.confirm_plan(plan.plan_id, _ctx(), plan.version)
    assert repeated.repeated and repeated.results[0].outcome == "unknown"
    assert adapter.read_state().version == expected_writes

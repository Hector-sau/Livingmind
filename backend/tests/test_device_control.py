"""Direct device control and its undo window.

The rule this file pins down: a low-risk control executes without a dialog, and the
safety net is a real reverse write of the value the device actually held — not a guessed
opposite command, and not a second confirmation nobody reads.
"""

import pytest

from app import config
from tests.conftest import ctx


def control(client, device: str, value: float):
    return client.post(
        "/api/spaces/space-home-bedroom/devices/control",
        json={"context": ctx(), "device": device, "value": value},
    )


def undo(client, undo_id: str):
    return client.post(f"/api/devices/undo/{undo_id}", json={"context": ctx()})


def state(client) -> dict:
    return client.get("/api/spaces/space-home-bedroom/devices", params={"accountId": "demo-account"}).json()


def test_a_control_executes_at_once_and_offers_an_undo(client):
    before = state(client)["lightBrightness"]
    body = control(client, "light", 20).json()

    assert body["result"]["outcome"] == "succeeded"
    assert body["deviceState"]["lightBrightness"] == 20
    assert body["result"]["observedValue"] == 20, "the value is read back, not assumed"

    window = body["undo"]
    assert window is not None
    assert window["previousValue"] == before
    assert window["appliedValue"] == 20


def test_undo_restores_the_exact_previous_value_not_a_guessed_opposite(client):
    # Put the light somewhere unremarkable first, so "undo off" has a real value to return to.
    control(client, "light", 30)
    body = control(client, "light", 0).json()
    assert state(client)["lightBrightness"] == 0

    restored = undo(client, body["undo"]["undoId"]).json()
    assert restored["restoredValue"] == 30
    assert restored["deviceState"]["lightBrightness"] == 30, "undoing 'off' must not jump to 100%"
    assert restored["result"]["outcome"] == "succeeded"


def test_the_window_closes_and_a_late_undo_is_refused(client, clock):
    body = control(client, "light", 45).json()
    clock.advance(seconds=config.UNDO_WINDOW_S + 1)

    late = undo(client, body["undo"]["undoId"])
    assert late.json()["error"]["code"] == "UNDO_EXPIRED"
    assert state(client)["lightBrightness"] == 45, "an expired window leaves the device alone"


def test_an_undo_can_only_be_used_once(client):
    control(client, "light", 60)
    body = control(client, "light", 15).json()
    undo_id = body["undo"]["undoId"]

    assert undo(client, undo_id).json()["restoredValue"] == 60
    again = undo(client, undo_id)
    assert again.json()["error"]["code"] == "UNDO_EXPIRED"
    assert state(client)["lightBrightness"] == 60


def test_a_newer_control_supersedes_the_older_offer(client):
    first = control(client, "light", 70).json()["undo"]["undoId"]
    second = control(client, "light", 25).json()["undo"]["undoId"]

    stale = undo(client, first)
    assert stale.json()["error"]["code"] == "UNDO_EXPIRED", "only the latest change is undoable"

    assert undo(client, second).json()["deviceState"]["lightBrightness"] == 70


def test_a_reset_invalidates_a_pending_undo(client):
    body = control(client, "light", 35).json()
    client.post("/api/demo/reset", params={"accountId": "demo-account"})

    refused = undo(client, body["undo"]["undoId"])
    assert refused.json()["error"]["code"] in {"UNDO_INVALIDATED", "UNDO_EXPIRED"}


def test_control_still_goes_through_the_whitelist_and_range_checks(client):
    too_cold = control(client, "ac", 5).json()
    assert too_cold["result"]["outcome"] == "rejected"
    assert "范围" in (too_cold["result"]["reason"] or "")
    assert too_cold["undo"] is None, "a refused write has nothing to undo"

    fractional = control(client, "light", 20.5).json()
    assert fractional["result"]["outcome"] == "rejected"
    assert fractional["undo"] is None


def test_a_write_that_changes_nothing_offers_no_undo(client):
    control(client, "light", 40)
    again = control(client, "light", 40).json()
    assert again["result"]["outcome"] == "succeeded"
    assert again["undo"] is None, "there is nothing to put back"


def test_control_is_recorded_with_its_source(client):
    control(client, "curtain", 0)
    kinds = [a["kind"] for a in client.get("/api/spaces/space-home-bedroom/activity", params={"accountId": "demo-account"}).json()["items"]]
    assert "device_controlled" in kinds

    body = control(client, "curtain", 80).json()
    undo(client, body["undo"]["undoId"])
    kinds = [a["kind"] for a in client.get("/api/spaces/space-home-bedroom/activity", params={"accountId": "demo-account"}).json()["items"]]
    assert "device_control_undone" in kinds


def test_control_rejects_a_mismatched_context(client):
    wrong = client.post(
        "/api/spaces/space-home-bedroom/devices/control",
        json={"context": {**ctx(), "spaceId": "space-other"}, "device": "light", "value": 10},
    )
    assert wrong.json()["error"]["code"] == "FORBIDDEN_CONTEXT"


def test_control_works_while_a_rest_service_runs(client):
    plan = client.post("/api/plans/rest", json={"context": ctx(), "utterance": "我想休息"}).json()
    client.post(f"/api/plans/{plan['planId']}/confirm", json={"context": ctx(), "planVersion": plan["version"]})

    body = control(client, "light", 55).json()
    assert body["result"]["outcome"] == "succeeded", "a person in the room can still adjust the light"
    assert body["undo"] is not None


@pytest.mark.parametrize("device,value", [("light", 20), ("ac", 24), ("curtain", 50)])
def test_every_supported_device_can_be_controlled_and_undone(client, device, value):
    before = control(client, device, value).json()["undo"]["previousValue"]
    body = control(client, device, value + 5).json()
    assert body["undo"]["previousValue"] == value
    restored = undo(client, body["undo"]["undoId"]).json()
    assert restored["restoredValue"] == value
    assert before is not None

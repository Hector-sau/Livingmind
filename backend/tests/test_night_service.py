"""Step 7 acceptance: one serviceId runs the whole night on a simulated clock.

- the rest plan carries the overnight schedule, confirmed together with the plan
- advancing the clock runs each due step exactly once, through the executor
- the last wake-up step completes the service
- stop cancels every remaining step; later advances are refused
"""

import threading

from app.adapters.virtual.devices import VirtualDeviceAdapter
from app.demo import seed
from tests.conftest import ctx
from tests.test_events import SPACE, devices, event, kinds, make, start_rest


def advance(client, service_id, minutes=None, person="person-lin", status=200):
    body = {"context": ctx(person)}
    if minutes is not None:
        body["minutes"] = minutes
    res = client.post(f"/api/services/{service_id}/clock/advance", json=body)
    assert res.status_code == status, res.text
    return res.json()


def test_rest_plan_carries_the_overnight_schedule_and_trace_mentions_it():
    client, _, _ = make()
    reply = client.post("/api/assistant/messages", json={"context": ctx("person-lin"), "text": "我想休息"}).json()
    plan = reply["plan"]
    assert [s["at"] for s in plan["schedule"]] == ["23:00", "01:00", "06:30", "06:45", "07:00"]
    assert [s["phase"] for s in plan["schedule"]] == ["sleep", "deep", "wake", "wake", "wake"]
    assert all(s["status"] == "pending" and s["source"] == "rule" for s in plan["schedule"])
    assert any("整晚安排" in n for n in plan["notes"])
    exec_step = next(t for t in plan["trace"] if t["agent"] == "space_execution")
    assert "整晚安排 5 个定时步骤" in exec_step["detail"]
    # 林悦 prefers 25 °C: deep night raises to 26 °C, wake-up returns to 25 °C, light ends at the rest cap
    deep = plan["schedule"][1]["actions"]
    assert [(a["device"], a["value"]) for a in deep] == [("ac", 26.0)]
    last = plan["schedule"][-1]["actions"]
    assert {a["device"]: a["value"] for a in last} == {"curtain": 100, "light": seed.WAKE_LIGHT_MAX}


def test_device_commands_have_no_schedule():
    client, _, _ = make()
    reply = client.post("/api/assistant/messages", json={"context": ctx("person-lin"), "text": "把灯关了"}).json()
    assert reply["plan"]["schedule"] == []


def test_deep_night_raise_stays_inside_the_preference_band():
    client, _, _ = make()
    # 陈川 22 °C; eco mode may raise the evening target, the deep-night step never exceeds preference + 3 °C
    client.put(f"/api/spaces/{SPACE}/energy-mode", json={"context": ctx("person-chen"), "mode": "eco"})
    plan = client.post("/api/assistant/messages", json={"context": ctx("person-chen"), "text": "我想休息"}).json()["plan"]
    deep_ac = plan["schedule"][1]["actions"][0]["value"]
    assert deep_ac <= 22 + 3


def test_service_starts_the_night_clock_and_steps_run_once_in_order():
    client, _, _ = make()
    svc = start_rest(client)
    assert svc["nightClock"] == "22:30" and svc["nightOffsetMin"] == 0
    assert all(s["status"] == "pending" for s in svc["schedule"])

    r = advance(client, svc["serviceId"])  # jump to the next step
    assert r["service"]["nightClock"] == "23:00"
    assert [s["at"] for s in r["executed"]] == ["23:00"]
    assert devices(client)["lightBrightness"] == 0

    r = advance(client, svc["serviceId"], minutes=30)  # 23:30: nothing due
    assert r["executed"] == [] and r["note"] == "下一步在 01:00"
    assert r["service"]["nightClock"] == "23:30"

    r = advance(client, svc["serviceId"], minutes=600)  # far past the end: clamps to 07:00, runs the rest once
    assert [s["at"] for s in r["executed"]] == ["01:00", "06:30", "06:45", "07:00"]
    assert r["service"]["nightClock"] == "07:00"
    assert r["service"]["status"] == "completed" and r["service"]["stoppedAt"]
    assert all(s["status"] == "done" for s in r["service"]["schedule"])
    d = devices(client)
    assert (d["lightBrightness"], d["acTargetTempC"], d["curtainOpenPercent"]) == (60, 25.0, 100)

    # completed: no more advances, stop is refused, events are ignored
    err = advance(client, svc["serviceId"], status=409)
    assert err["error"]["code"] == "SERVICE_NOT_ACTIVE"
    assert event(client, 30)["outcome"] == "ignored"
    k = kinds(client)
    assert k.count("schedule_step_executed") == 5 and "service_completed" in k and "clock_advanced" in k


def test_a_new_rest_plan_can_start_after_completion():
    client, _, _ = make()
    svc = start_rest(client)
    advance(client, svc["serviceId"], minutes=720)
    again = start_rest(client)
    assert again["status"] == "active" and again["serviceId"] != svc["serviceId"]


def test_stop_cancels_remaining_steps_and_blocks_later_advances():
    client, _, _ = make()
    svc = start_rest(client)
    advance(client, svc["serviceId"])  # 23:00 done
    stop = client.post(f"/api/services/{svc['serviceId']}/stop", json={"context": ctx("person-lin")}).json()
    statuses = [s["status"] for s in stop["service"]["schedule"]]
    assert statuses == ["done", "cancelled", "cancelled", "cancelled", "cancelled"]
    before = devices(client)
    err = advance(client, svc["serviceId"], status=409)
    assert err["error"]["code"] == "SERVICE_NOT_ACTIVE"
    assert devices(client) == before
    assert "schedule_cancelled" in kinds(client)


def test_other_person_or_space_cannot_advance():
    client, _, _ = make()
    svc = start_rest(client)
    bad = dict(ctx("person-lin"), spaceId="space-nowhere")
    res = client.post(f"/api/services/{svc['serviceId']}/clock/advance", json={"context": bad})
    assert res.status_code == 403
    res = client.post("/api/services/svc-missing/clock/advance", json={"context": ctx("person-lin")})
    assert res.status_code == 404


class GateAdapter(VirtualDeviceAdapter):
    """Blocks the first write after `armed` until released."""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.armed = False
        self.started = threading.Event()
        self.release = threading.Event()
        self.writes = 0

    def _before_write(self, device, command, value):
        if not self.armed:
            return
        self.writes += 1
        if self.writes == 1:
            self.started.set()
            assert self.release.wait(timeout=5), "test did not release the device"


def test_concurrent_advances_never_run_a_step_twice():
    client, svc_obj, _ = make(adapter_cls=GateAdapter)
    adapter = svc_obj._devices[SPACE]
    svc = start_rest(client)
    adapter.armed = True
    out = {}
    t = threading.Thread(target=lambda: out.setdefault("first", advance(client, svc["serviceId"], minutes=720)))
    t.start()
    assert adapter.started.wait(timeout=5)
    second = advance(client, svc["serviceId"], minutes=720)  # lands while the first is mid-write
    assert second["executed"] == [] and second["note"] == "上一次推进仍在进行"
    adapter.release.set()
    t.join(timeout=5)
    first = out["first"]
    assert [s["at"] for s in first["executed"]] == ["23:00", "01:00", "06:30", "06:45", "07:00"]
    # 1 + 1 + 2 + 3 + 2 actions, each written exactly once
    assert adapter.writes == 9
    assert kinds(client).count("schedule_step_executed") == 5


def test_stop_during_an_advance_cancels_the_running_and_remaining_steps():
    client, svc_obj, _ = make(adapter_cls=GateAdapter)
    adapter = svc_obj._devices[SPACE]
    svc = start_rest(client)
    adapter.armed = True
    out = {}
    t = threading.Thread(target=lambda: out.setdefault("adv", advance(client, svc["serviceId"], minutes=720)))
    t.start()
    assert adapter.started.wait(timeout=5)  # 23:00 light-off write is in flight
    stop = client.post(f"/api/services/{svc['serviceId']}/stop", json={"context": ctx("person-lin")})
    assert stop.status_code == 200  # never blocked by the slow device
    adapter.release.set()
    t.join(timeout=5)
    adv = out["adv"]
    statuses = [s["status"] for s in adv["service"]["schedule"]]
    assert statuses[0] == "done"  # the write that was already in flight finished
    assert statuses[1:] == ["cancelled"] * 4
    assert adv["service"]["status"] == "stopped"
    assert adapter.writes == 1  # nothing after the stop reached a device
    d = devices(client)
    assert d["acTargetTempC"] == 25.0 and d["curtainOpenPercent"] == 0


def test_reset_clears_the_night():
    client, svc_obj, _ = make()
    svc = start_rest(client)
    advance(client, svc["serviceId"])
    client.post("/api/demo/reset", params={"accountId": "demo-account"})
    boot = client.get("/api/bootstrap", params={"accountId": "demo-account"}).json()
    assert boot["activeService"] is None
    assert not svc_obj._store.has_flag(svc["serviceId"], "advancing")


def test_reset_invalidates_an_overnight_write_already_in_flight():
    client, svc_obj, _ = make(adapter_cls=GateAdapter)
    adapter = svc_obj._devices[SPACE]
    service = start_rest(client)
    adapter.armed = True
    out = {}
    t = threading.Thread(target=lambda: out.setdefault("advance", advance(client, service["serviceId"], minutes=720)))
    t.start()
    assert adapter.started.wait(timeout=5)

    reset = client.post("/api/demo/reset", params={"accountId": "demo-account"})
    assert reset.status_code == 200
    adapter.release.set()
    t.join(timeout=5)

    old = out["advance"]
    assert old["service"]["status"] == "stopped"
    assert all(step["status"] == "cancelled" for step in old["service"]["schedule"])
    assert adapter.writes == 1
    state = devices(client)
    assert (state["lightBrightness"], state["acTargetTempC"], state["curtainOpenPercent"], state["version"]) == (
        80,
        26.0,
        100,
        0,
    )
    boot = client.get("/api/bootstrap", params={"accountId": "demo-account"}).json()
    assert boot["activeService"] is None
    assert kinds(client) == ["demo_reset"]


def test_requested_wake_time_and_explicit_simulated_sleep_are_visible():
    client, _, _ = make()
    plan = client.post(
        "/api/plans/rest", json={"context": ctx(), "utterance": "我想休息", "wakeTime": "06:30"}
    ).json()
    assert plan["wakeTime"] == "06:30"
    assert plan["schedule"][-1]["at"] == "06:30"
    confirmed = client.post(
        f"/api/plans/{plan['planId']}/confirm", json={"context": ctx(), "planVersion": plan["version"]}
    ).json()
    service_id = confirmed["service"]["serviceId"]

    sleep = client.post(f"/api/services/{service_id}/sleep", json={"context": ctx()})
    assert sleep.status_code == 200, sleep.text
    body = sleep.json()
    assert body["note"] == "已模拟入睡，灯光已按计划关闭"
    assert body["service"]["sleepDetectedAt"] is not None
    assert body["service"]["schedule"][0]["status"] == "done"
    assert devices(client)["lightBrightness"] == 0


def test_event_is_ignored_while_an_overnight_step_is_writing():
    client, svc_obj, _ = make(adapter_cls=GateAdapter, cooldown=0)
    adapter = svc_obj._devices[SPACE]
    service = start_rest(client)
    adapter.armed = True
    out = {}
    t = threading.Thread(target=lambda: out.setdefault("advance", advance(client, service["serviceId"])))
    t.start()
    assert adapter.started.wait(timeout=5)
    event_res = event(client, 30)
    assert event_res["outcome"] == "ignored"
    assert event_res["reason"] == "整晚安排正在执行，请稍后重试"
    adapter.release.set()
    t.join(timeout=5)


class FailingAdapter(VirtualDeviceAdapter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.armed = False

    def _before_write(self, device, command, value):
        if self.armed:
            raise RuntimeError("simulated device offline")


def test_all_failed_overnight_actions_mark_the_service_failed_not_completed():
    client, svc_obj, _ = make(adapter_cls=FailingAdapter)
    service = start_rest(client)
    svc_obj._devices[SPACE].armed = True
    result = advance(client, service["serviceId"], minutes=720)
    assert result["service"]["status"] == "failed"
    assert all(step["status"] == "cancelled" for step in result["service"]["schedule"])
    assert "service_failed" in kinds(client)


class CurtainFailingAdapter(VirtualDeviceAdapter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.armed = False

    def _before_write(self, device, command, value):
        if self.armed and device == "curtain":
            raise RuntimeError("simulated curtain offline")


def test_partial_wake_device_failures_mark_steps_and_service_failed():
    client, svc_obj, _ = make(adapter_cls=CurtainFailingAdapter)
    service = start_rest(client)
    svc_obj._devices[SPACE].armed = True
    result = advance(client, service["serviceId"], minutes=720)

    assert result["service"]["status"] == "failed"
    assert [step["status"] for step in result["service"]["schedule"]] == [
        "done",
        "done",
        "cancelled",
        "cancelled",
        "cancelled",
    ]
    failed = [item for item in result["results"] if item["outcome"] == "failed"]
    assert len(failed) == 3 and all(item["device"] == "curtain" for item in failed)
    assert devices(client)["curtainOpenPercent"] == 0
    assert "service_failed" in kinds(client)

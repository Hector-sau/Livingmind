"""Step 6 acceptance: one automatic adjustment triggered by a simulated room-temperature event."""

import json
import threading

from fastapi.testclient import TestClient

from app.adapters.virtual.devices import VirtualDeviceAdapter
from app.agents.experience.provider import ProviderError
from app.demo import seed
from app.main import create_app
from app.services.planner import Planner
from app.services.rest_service import RestService, get_rest_service
from tests.conftest import FakeClock, ctx

SPACE = "space-home-bedroom"


class FakeProvider:
    name, model = "fake", "fake-1"

    def __init__(self, reply=None, error=None):
        self.reply, self.error, self.calls = reply, error, []

    def complete_json(self, system, user, timeout_s):
        self.calls.append(user)
        if self.error:
            raise self.error
        return json.dumps(self.reply, ensure_ascii=False)


def make(provider=None, default_mode="rule", cooldown=30, max_adj=3, adapter_cls=None):
    clock = FakeClock()
    svc = RestService(
        clock=clock,
        planner=Planner(default_mode, provider, 6, clock),
        event_cooldown_s=cooldown,
        event_max_adjustments=max_adj,
    )
    if adapter_cls:
        svc._devices[SPACE] = adapter_cls(SPACE, seed.INITIAL_DEVICE_STATE, clock)
    # A test may build several independent backends. In SQL mode they share one database,
    # so start each from an empty store, the way a fresh process would.
    svc._store.clear()
    app = create_app()
    app.dependency_overrides[get_rest_service] = lambda: svc
    return TestClient(app), svc, clock


def start_rest(client, mode=None, person="person-lin"):
    body = {"context": ctx(person), "utterance": "我想休息"}
    if mode:
        body["mode"] = mode
    plan = client.post("/api/plans/rest", json=body).json()
    res = client.post(f"/api/plans/{plan['planId']}/confirm", json={"context": ctx(person), "planVersion": 1}).json()
    return res["service"]


def event(client, temp, person="person-lin"):
    res = client.post(
        f"/api/spaces/{SPACE}/events",
        json={"context": ctx(person), "type": "room_temperature_changed", "roomTempC": temp},
    )
    assert res.status_code == 200, res.text
    return res.json()


def devices(client):
    return client.get(f"/api/spaces/{SPACE}/devices", params={"accountId": "demo-account"}).json()


def kinds(client):
    items = client.get(f"/api/spaces/{SPACE}/activity", params={"accountId": "demo-account"}).json()["items"]
    return [i["kind"] for i in items]


# 1
def test_event_without_active_service_is_ignored():
    client, _, _ = make()
    before = devices(client)
    r = event(client, 30)
    assert r["outcome"] == "ignored" and "没有运行中的服务" in r["reason"]
    assert r["source"] == "simulated"
    assert devices(client) == before
    assert kinds(client)[:2] == ["event_ignored", "event_received"]


# 2
def test_event_adjusts_active_service_once_and_reads_back():
    client, _, _ = make()
    svc = start_rest(client)  # lin: AC 25
    version = devices(client)["version"]
    r = event(client, 28)
    assert r["outcome"] == "adjusted"
    assert r["plan"]["scenario"] == "rest_adjustment" and r["plan"]["source"] == "rule"
    assert [(a["device"], a["value"]) for a in r["plan"]["actions"]] == [("ac", 24.0)]  # only what changed
    assert [x["outcome"] for x in r["results"]] == ["succeeded"]
    assert r["deviceState"]["acTargetTempC"] == 24.0 and r["deviceState"]["version"] == version + 1
    assert r["service"]["adjustments"] == 1 and r["service"]["serviceId"] == svc["serviceId"]
    assert devices(client)["acTargetTempC"] == 24.0
    k = kinds(client)
    assert k[0] == "action_executed" and "service_adjusted" in k and "event_received" in k


def test_comfortable_room_needs_no_adjustment():
    client, _, _ = make()
    start_rest(client)
    r = event(client, 25.5)
    assert r["outcome"] == "ignored" and "无需调整" in r["reason"]
    assert r["service"]["adjustments"] == 0


# 3
def test_second_event_within_cooldown_is_ignored(clock=None):
    client, _, clock = make(cooldown=30)
    start_rest(client)
    assert event(client, 28)["outcome"] == "adjusted"
    clock.advance(seconds=10)
    r = event(client, 28)
    assert r["outcome"] == "ignored" and "冷却中" in r["reason"]
    clock.advance(seconds=25)
    r = event(client, 28)
    assert r["outcome"] == "adjusted" and r["deviceState"]["acTargetTempC"] == 23.0


# 4
def test_events_stop_after_max_adjustments_and_respect_preference_band():
    client, _, clock = make(cooldown=0, max_adj=5)
    start_rest(client)  # AC 25; band is 22..28
    temps = []
    for _ in range(5):
        r = event(client, 35)
        temps.append((r["outcome"], r["deviceState"]["acTargetTempC"]))
    # 24, 23, 22, then at the band edge -> no further change
    assert temps[:3] == [("adjusted", 24.0), ("adjusted", 23.0), ("adjusted", 22.0)]
    assert temps[3][0] == "ignored" and temps[3][1] == 22.0

    client, _, _ = make(cooldown=0, max_adj=2)
    start_rest(client)
    assert event(client, 35)["outcome"] == "adjusted"
    assert event(client, 35)["outcome"] == "adjusted"
    r = event(client, 35)
    assert r["outcome"] == "ignored" and "上限" in r["reason"]


# 5
def test_event_after_stop_is_ignored_and_devices_unchanged():
    client, _, _ = make(cooldown=0)
    svc = start_rest(client)
    client.post(f"/api/services/{svc['serviceId']}/stop", json={"context": ctx()})
    before = devices(client)
    r = event(client, 30)
    assert r["outcome"] == "ignored"
    assert devices(client) == before


# 6
def test_model_mode_event_uses_model_and_falls_back_with_label():
    good = {
        "goal": "室温偏高，空调略降",
        "rationale": "保持安静，只调空调",
        "light_brightness": 15,
        "ac_target_temp_c": 23,
        "curtain_open_percent": 0,
        "needs_clarification": False,
        "clarification_question": None,
    }
    provider = FakeProvider(reply={**good, "ac_target_temp_c": 25})  # rest plan keeps 25°C
    client, _, _ = make(provider, cooldown=0)
    start_rest(client, mode="model")
    provider.reply = good  # the event adjustment proposes 23°C
    r = event(client, 28)
    assert r["plan"]["source"] == "model" and [(a["device"], a["value"]) for a in r["plan"]["actions"]] == [("ac", 23.0)]
    assert "室温现在是 28°C" in provider.calls[-1] and "林悦" in provider.calls[-1]

    provider.error = ProviderError("timeout", "模型响应超过 6 秒")
    r = event(client, 28)
    assert r["plan"]["source"] == "rule_fallback" and "超过" in r["plan"]["generation"]["fallbackReason"]
    assert r["deviceState"]["acTargetTempC"] == 22.0  # rule step from 23

    provider2 = FakeProvider(reply={**good, "ac_target_temp_c": 25})
    client2, _, _ = make(provider2, cooldown=0)
    start_rest(client2, mode="model")
    provider2.reply = {**good, "light_brightness": 100}  # beyond the deviation limit
    r = event(client2, 28)
    assert r["plan"]["source"] == "rule_fallback" and "偏离偏好过大" in r["plan"]["generation"]["fallbackReason"]
    assert r["deviceState"]["lightBrightness"] != 100


def test_rule_mode_service_never_calls_model_on_events():
    provider = FakeProvider(reply={})
    client, _, _ = make(provider, default_mode="model", cooldown=0)
    start_rest(client, mode="rule")
    before_calls = len(provider.calls)
    assert event(client, 28)["plan"]["source"] == "rule"
    assert len(provider.calls) == before_calls


# 7
class SlowAdapter(VirtualDeviceAdapter):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.block_next = threading.Event()
        self.started = threading.Event()
        self.release = threading.Event()

    def _before_write(self, device, command, value):
        if self.block_next.is_set():
            self.block_next.clear()
            self.started.set()
            assert self.release.wait(timeout=5)


def test_stop_during_adjustment_skips_remaining_and_blocks_later_events():
    reply = {
        "goal": "降温并再调暗",
        "rationale": "x",
        "light_brightness": 5,
        "ac_target_temp_c": 23,
        "curtain_open_percent": 0,
        "needs_clarification": False,
        "clarification_question": None,
    }
    provider = FakeProvider(reply={**reply, "light_brightness": 15, "ac_target_temp_c": 25})
    client, svc_obj, _ = make(provider, cooldown=0, adapter_cls=SlowAdapter)
    service = start_rest(client, mode="model")
    provider.reply = reply  # adjustment changes light and AC -> two actions
    adapter = svc_obj._devices[SPACE]
    adapter.block_next.set()

    out = {}
    t = threading.Thread(target=lambda: out.setdefault("r", event(client, 28)))
    t.start()
    assert adapter.started.wait(timeout=5)

    # while the first adjustment write is in flight: a second event is refused, and stop goes through
    assert "仍在进行" in event(client, 28)["reason"]
    stop = client.post(f"/api/services/{service['serviceId']}/stop", json={"context": ctx()})
    assert stop.status_code == 200

    adapter.release.set()
    t.join(timeout=5)
    r = out["r"]
    assert [x["outcome"] for x in r["results"]] == ["succeeded", "skipped"]
    version = devices(client)["version"]
    assert event(client, 28)["outcome"] == "ignored"
    assert devices(client)["version"] == version


def test_event_space_must_match_context():
    client, _, _ = make()
    res = client.post(
        "/api/spaces/space-other/events",
        json={"context": ctx(), "type": "room_temperature_changed", "roomTempC": 28},
    )
    assert res.status_code == 403

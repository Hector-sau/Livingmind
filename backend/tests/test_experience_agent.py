"""Step 5 acceptance: Experience Agent + planner modes + fallback. Uses a test double provider —
these tests never call DeepSeek. A real call is verified separately with scripts/try_model.py."""

import json
import logging

import httpx
import pytest
from fastapi.testclient import TestClient

from app.agents.experience.provider import DeepSeekProvider, ProviderError
from app.main import create_app
from app.services.planner import Planner
from app.services.rest_service import RestService, get_rest_service
from tests.conftest import FakeClock, ctx

SPACE = "space-home-bedroom"
GOOD = {
    "goal": "安静昏暗、略凉的休息环境",
    "rationale": "用户说有点热，比偏好再低 1 度",
    "light_brightness": 10,
    "ac_target_temp_c": 24,
    "curtain_open_percent": 0,
    "needs_clarification": False,
    "clarification_question": None,
}


class FakeProvider:
    """Records prompts; returns a canned reply or raises."""

    name = "fake"
    model = "fake-1"

    def __init__(self, reply=None, error: ProviderError | None = None):
        self.reply = reply if reply is not None else json.dumps(GOOD, ensure_ascii=False)
        self.error = error
        self.calls: list[tuple[str, str]] = []

    def complete_json(self, system, user, timeout_s):
        self.calls.append((system, user))
        if self.error:
            raise self.error
        return self.reply


def make(provider, default_mode="model"):
    clock = FakeClock()
    planner = Planner(default_mode, provider, timeout_s=6, clock=clock)
    svc = RestService(clock=clock, planner=planner)
    app = create_app()
    app.dependency_overrides[get_rest_service] = lambda: svc
    return TestClient(app), svc


def plan(client, person="person-lin", mode=None, utterance="我想休息，有点热"):
    body = {"context": ctx(person), "utterance": utterance}
    if mode:
        body["mode"] = mode
    res = client.post("/api/plans/rest", json=body)
    assert res.status_code == 200, res.text
    return res.json()


def devices(client):
    return client.get(f"/api/spaces/{SPACE}/devices", params={"accountId": "demo-account"}).json()


# 1. valid model output -> plan, but creating it does not touch devices
def test_model_output_becomes_plan_without_touching_devices():
    client, _ = make(FakeProvider())
    before = devices(client)
    p = plan(client)
    assert p["source"] == "model"
    assert p["summary"] == GOOD["goal"]
    assert [a["value"] for a in p["actions"]] == [10, 24, 0]
    assert p["generation"]["provider"] == "fake" and p["generation"]["model"] == "fake-1"
    assert p["generation"]["fallbackReason"] is None
    assert devices(client) == before


# 2. model plan is executed through the same executor and read back
def test_model_plan_executes_via_executor_and_reads_back():
    client, _ = make(FakeProvider())
    p = plan(client)
    res = client.post(f"/api/plans/{p['planId']}/confirm", json={"context": ctx(), "planVersion": 1})
    assert res.status_code == 200
    body = res.json()
    assert [r["outcome"] for r in body["results"]] == ["succeeded"] * 3
    d = body["deviceState"]
    assert (d["lightBrightness"], d["acTargetTempC"], d["curtainOpenPercent"]) == (10, 24.0, 0)
    assert d["source"] == "virtual_device"


# 3. timeout -> rule fallback, labelled
def test_timeout_falls_back_to_rule_with_reason():
    client, _ = make(FakeProvider(error=ProviderError("timeout", "模型响应超过 6 秒")))
    p = plan(client)
    assert p["source"] == "rule_fallback"
    assert p["generation"]["modeRequested"] == "model"
    assert "超过" in p["generation"]["fallbackReason"]
    assert [a["value"] for a in p["actions"]] == [15, 25.0, 0]  # person-lin's own preference
    kinds = [i["kind"] for i in client.get(f"/api/spaces/{SPACE}/activity", params={"accountId": "demo-account"}).json()["items"]]
    assert "plan_fallback" in kinds


def test_unconfigured_model_falls_back_to_rule():
    client, _ = make(None)
    p = plan(client, mode="model")
    assert p["source"] == "rule_fallback" and "未配置" in p["generation"]["fallbackReason"]
    boot = client.get("/api/bootstrap", params={"accountId": "demo-account"}).json()
    assert boot["planner"]["modelConfigured"] is False


# 4. bad JSON / out-of-range / unknown fields cannot bypass validation
@pytest.mark.parametrize(
    "reply",
    [
        "not json at all",
        json.dumps({**GOOD, "ac_target_temp_c": 5}),
        json.dumps({**GOOD, "light_brightness": 150}),
        json.dumps({**GOOD, "curtain_open_percent": 12.5}),
        json.dumps({**GOOD, "device": "heater", "command": "set_power"}),
        json.dumps({k: v for k, v in GOOD.items() if k != "goal"}),
    ],
)
def test_invalid_model_output_falls_back_and_never_reaches_devices(reply):
    client, _ = make(FakeProvider(reply=reply))
    before = devices(client)
    p = plan(client)
    assert p["source"] == "rule_fallback"
    assert p["generation"]["fallbackReason"]
    for a in p["actions"]:
        assert 0 <= a["value"] <= 100
    assert devices(client) == before


def test_code_fenced_json_is_accepted():
    client, _ = make(FakeProvider(reply="```json\n" + json.dumps(GOOD, ensure_ascii=False) + "\n```"))
    assert plan(client)["source"] == "model"


# 5. each person's own preference goes into the prompt
def test_prompts_use_each_persons_own_preferences():
    provider = FakeProvider()
    client, _ = make(provider)
    plan(client, "person-lin")
    plan(client, "person-chen")
    _, user_a = provider.calls[0]
    _, user_b = provider.calls[1]
    assert "林悦" in user_a and "灯光 15%" in user_a and "陈川" not in user_a
    assert "陈川" in user_b and "灯光 30%" in user_b and "林悦" not in user_b


# 6. rule mode never calls the model
def test_rule_mode_never_calls_provider():
    provider = FakeProvider()
    client, _ = make(provider, default_mode="rule")
    p = plan(client)
    assert p["source"] == "rule" and provider.calls == []
    p = plan(client, mode="rule")
    assert p["source"] == "rule" and provider.calls == []
    p = plan(client, mode="model")
    assert p["source"] == "model" and len(provider.calls) == 1


# 7. model failure does not disturb stop / repeat-confirm / expiry semantics
def test_model_failure_keeps_existing_semantics(clock):
    provider = FakeProvider(error=ProviderError("network", "无法连接模型服务：ConnectError"))
    planner = Planner("model", provider, 6, clock)
    svc = RestService(clock=clock, planner=planner)
    app = create_app()
    app.dependency_overrides[get_rest_service] = lambda: svc
    client = TestClient(app)

    p = plan(client)
    assert p["source"] == "rule_fallback"
    first = client.post(f"/api/plans/{p['planId']}/confirm", json={"context": ctx(), "planVersion": 1}).json()
    again = client.post(f"/api/plans/{p['planId']}/confirm", json={"context": ctx(), "planVersion": 1}).json()
    assert again["repeated"] is True
    stop = client.post(f"/api/services/{first['service']['serviceId']}/stop", json={"context": ctx()})
    assert stop.status_code == 200
    stale = plan(client)
    clock.advance(minutes=11)
    res = client.post(f"/api/plans/{stale['planId']}/confirm", json={"context": ctx(), "planVersion": 1})
    assert res.json()["error"]["code"] in ("PLAN_EXPIRED", "PLAN_INVALIDATED")


# 8. the API key never appears in errors or logs
def test_api_key_never_leaks(caplog, monkeypatch):
    secret = "sk-SECRET-1234567890"

    def boom(*a, **kw):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx, "post", boom)
    provider = DeepSeekProvider(secret, "deepseek-flash")
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(ProviderError) as ei:
            provider.complete_json("s", "u", 1.0)
    assert secret not in str(ei.value)
    assert secret not in caplog.text
    assert ei.value.kind == "network"


def test_deepseek_provider_maps_http_and_empty_errors(monkeypatch):
    def make_resp(status, payload):
        return httpx.Response(status, json=payload, request=httpx.Request("POST", "https://api.deepseek.com/chat/completions"))

    provider = DeepSeekProvider("sk-x", "deepseek-flash")
    monkeypatch.setattr(httpx, "post", lambda *a, **kw: make_resp(401, {"error": "bad key"}))
    with pytest.raises(ProviderError) as ei:
        provider.complete_json("s", "u", 1.0)
    assert ei.value.kind == "http" and "401" in ei.value.message and "sk-x" not in ei.value.message

    monkeypatch.setattr(httpx, "post", lambda *a, **kw: make_resp(200, {"choices": []}))
    with pytest.raises(ProviderError) as ei:
        provider.complete_json("s", "u", 1.0)
    assert ei.value.kind == "empty"

    captured = {}

    def ok(url, headers, json, timeout):
        captured.update(url=url, headers=headers, body=json, timeout=timeout)
        return make_resp(200, {"choices": [{"message": {"content": "{\"a\":1}"}}]})

    monkeypatch.setattr(httpx, "post", ok)
    assert provider.complete_json("s", "u", 2.5) == '{"a":1}'
    assert captured["url"] == "https://api.deepseek.com/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer sk-x"
    assert captured["body"]["response_format"] == {"type": "json_object"}
    assert captured["body"]["model"] == "deepseek-flash" and captured["timeout"] == 2.5

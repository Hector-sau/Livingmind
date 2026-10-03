"""Development regressions, not an independent accuracy benchmark. No paid calls."""

import json

import pytest

from app.agents.orchestrator.agent import route_intent
from tests.conftest import ctx
from tests.test_experience_agent import FakeProvider, GOOD, make


@pytest.mark.parametrize("text", [
    "空调开了又关了，你确认一下",
    "窗帘打开又关上，你确认一下",
    "不要关灯",
    "别把窗帘拉开",
    "我想休息，只调空调，其他不要动",
    "我想睡觉，灯保持现在这样",
])
def test_unsafe_or_limited_requests_need_clarification(text):
    assert route_intent(text) == "clarification"


@pytest.mark.parametrize("utterance, override", [
    ("我想休息，灯光再暗一些", {"light_brightness": 30}),
    ("我想休息，空调调凉一点", {"ac_target_temp_c": 26}),
    ("我想休息，空调调暖一点", {"ac_target_temp_c": 24}),
    ("我想休息，窗帘打开一些", {"curtain_open_percent": 0}),
])
def test_schema_valid_but_wrong_direction_is_not_accepted(utterance, override):
    client, _ = make(FakeProvider(reply=json.dumps({**GOOD, **override})))
    response = client.post("/api/assistant/messages", json={
        "context": ctx(), "text": utterance, "mode": "model",
    })
    assert response.status_code == 200
    reply = response.json()
    assert reply["kind"] == "clarification" and reply["plan"] is None


def test_direct_command_clarification_uses_new_answer_not_old_conflicting_command():
    client, _ = make(None, "rule")
    body = {"context": ctx(), "mode": "rule", "conversationId": "negation-regression"}
    first = client.post("/api/assistant/messages", json={**body, "text": "不要关灯"}).json()
    assert first["kind"] == "clarification"
    second = client.post("/api/assistant/messages", json={**body, "text": "灯调到 20%"}).json()
    assert second["kind"] == "plan"
    assert [(a["device"], a["value"]) for a in second["plan"]["actions"]] == [("light", 20)]


def test_legacy_rest_endpoint_returns_clear_error_instead_of_asserting_on_clarification():
    client, _ = make(None, "rule")
    response = client.post("/api/plans/rest", json={
        "context": ctx(), "utterance": "我想休息，只调空调", "mode": "rule",
    })
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CLARIFICATION_REQUIRED"

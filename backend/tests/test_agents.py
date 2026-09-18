"""Step 8: main Agent routing and orchestration, Space Execution Agent, memory, energy rules."""

from datetime import datetime, timezone

import pytest

from app.adapters.virtual.devices import CAPABILITIES
from app.agents.orchestrator import route_intent
from app.agents.space_execution import SpaceExecutionAgent
from app.contracts import RestPreference
from app.demo import seed
from app.energy import EnergyIntelligence, comfort_band, estimate_load_kw, power_tier
from tests.conftest import ctx

SPACE = "space-home-bedroom"
AGENT_ORDER = ["orchestrator", "memory", "experience", "energy", "space_execution", "harness"]


def say(client, text, person="person-lin", mode=None):
    body = {"context": ctx(person), "text": text}
    if mode:
        body["mode"] = mode
    res = client.post("/api/assistant/messages", json=body)
    assert res.status_code == 200, res.text
    return res.json()


def devices(client):
    return client.get(f"/api/spaces/{SPACE}/devices", params={"accountId": "demo-account"}).json()


def confirm(client, plan, person="person-lin"):
    return client.post(f"/api/plans/{plan['planId']}/confirm", json={"context": ctx(person), "planVersion": 1}).json()


def energy_mode(client, mode, space=SPACE):
    return client.put(f"/api/spaces/{space}/energy-mode", json={"context": ctx(), "mode": mode})


# ---- routing ----


@pytest.mark.parametrize(
    "text, intent",
    [
        ("我想休息", "rest"),
        ("把灯关了，我要睡了", "rest"),  # rest words win: the full branch handles it
        ("把空调调到24度", "device_command"),
        ("关灯", "device_command"),
        ("打开窗帘", "device_command"),
        ("卧室现在几度", "status"),
        ("灯现在什么状态", "status"),
        ("今天股市怎么样", "other"),
        ("我不想休息，只想关灯", "device_command"),
        ("把那个调低一点", "clarification"),
        ("先开灯再关灯", "clarification"),
    ],
)
def test_router(text, intent):
    assert route_intent(text) == intent


# ---- full branch: 1 main agent + 2 specialist agents + memory + energy + harness ----


def test_rest_plan_carries_the_full_agent_trace(client):
    before = devices(client)
    reply = say(client, "我想休息")
    assert reply["kind"] == "plan" and reply["intent"] == "rest"
    plan = reply["plan"]
    assert [s["agent"] for s in plan["trace"]] == AGENT_ORDER
    assert all(s["ok"] for s in plan["trace"])
    memory_step = plan["trace"][1]
    assert "林悦" in memory_step["detail"] and "陈川" not in memory_step["detail"]
    assert plan["energy"]["source"] == "rule" and plan["energy"]["mode"] == "comfort_first"
    assert devices(client) == before  # planning never touches devices


def test_comfort_first_advises_but_keeps_the_target(client):
    plan = say(client, "我想休息")["plan"]  # FakeClock 12:00Z = 20:00 local -> peak
    e = plan["energy"]
    assert e["tariff"] == "peak" and e["recommendedAcC"] == 25.5 and e["applied"] is False
    assert [a["value"] for a in plan["actions"]] == [15, 25.0, 0]
    assert "只给建议" in e["reason"]


def test_eco_mode_applies_advice_inside_comfort_band_and_executes(client):
    assert energy_mode(client, "eco").json()["energyMode"] == "eco"
    plan = say(client, "我想休息")["plan"]
    e = plan["energy"]
    assert e["applied"] is True and e["recommendedAcC"] == 25.5
    assert e["comfortMinC"] <= 25.5 <= e["comfortMaxC"]
    assert e["loadKwAfter"] < e["loadKwBefore"]
    assert [a["value"] for a in plan["actions"]] == [15, 25.5, 0]
    assert any("节能模式" in n for n in plan["notes"])
    res = confirm(client, plan)
    assert res["deviceState"]["acTargetTempC"] == 25.5
    kinds = [i["kind"] for i in client.get(f"/api/spaces/{SPACE}/activity", params={"accountId": "demo-account"}).json()["items"]]
    assert "energy_mode_changed" in kinds


def test_offpeak_eco_changes_nothing(client, clock):
    energy_mode(client, "eco")
    clock.now = datetime(2026, 9, 17, 2, 0, tzinfo=timezone.utc)  # 10:00 local
    plan = say(client, "我想休息")["plan"]
    assert plan["energy"]["tariff"] == "offpeak" and plan["energy"]["applied"] is False
    assert plan["actions"][1]["value"] == 25.0


def test_energy_mode_space_must_match(client):
    assert energy_mode(client, "eco", space="space-other").status_code == 403


# ---- simplified branch: direct device command ----


def test_device_command_plan_confirm_without_service(client):
    reply = say(client, "把空调调到24度")
    assert reply["kind"] == "plan" and reply["intent"] == "device_command"
    plan = reply["plan"]
    assert plan["scenario"] == "device_command" and plan["energy"] is None
    assert [(a["device"], a["value"]) for a in plan["actions"]] == [("ac", 24.0)]
    assert [s["agent"] for s in plan["trace"]] == ["orchestrator", "space_execution", "harness"]
    res = confirm(client, plan)
    assert res["service"] is None
    assert res["deviceState"]["acTargetTempC"] == 24.0
    again = confirm(client, plan)
    assert again["repeated"] is True and again["deviceState"]["version"] == res["deviceState"]["version"]


def test_ambiguous_request_is_clarified_then_resumed_without_an_early_action(client):
    first = say(client, "把那个调低一点")
    assert first["kind"] == "clarification" and first["plan"] is None
    assert first["clarification"]["targetIntent"] == "device_command"
    assert devices(client)["version"] == 0

    resumed = say(client, "灯调到20%")
    assert resumed["kind"] == "plan"
    assert [(a["device"], a["value"]) for a in resumed["plan"]["actions"]] == [("light", 20.0)]


def test_negated_rest_with_explicit_command_uses_command_branch(client):
    reply = say(client, "我不想休息，只想关灯")
    assert reply["intent"] == "device_command"
    assert reply["plan"]["scenario"] == "device_command"


def test_pending_clarification_is_scoped_by_person_and_can_be_cancelled(client):
    assert say(client, "把那个调低一点", "person-lin")["kind"] == "clarification"
    assert say(client, "我想休息", "person-chen")["kind"] == "plan"
    cancelled = say(client, "算了", "person-lin")
    assert cancelled["kind"] == "answer" and "已取消" in cancelled["text"]
    assert say(client, "灯调到20%", "person-lin")["intent"] == "device_command"


def test_device_command_allowed_while_rest_service_runs(client):
    rest = say(client, "我想休息")["plan"]
    started = confirm(client, rest)
    assert started["service"]["status"] == "active"
    cmd = say(client, "打开窗帘")["plan"]
    res = confirm(client, cmd)
    assert res["deviceState"]["curtainOpenPercent"] == 100
    boot = client.get("/api/bootstrap", params={"accountId": "demo-account"}).json()
    assert boot["activeService"]["serviceId"] == started["service"]["serviceId"]


def test_device_command_out_of_range_is_blocked_by_harness(client):
    reply = say(client, "空调调到10度")
    assert reply["kind"] == "answer" and "没有生成动作" in reply["text"]
    assert reply["trace"][-1]["agent"] == "harness" and reply["trace"][-1]["ok"] is False
    assert devices(client)["version"] == 0


def test_device_command_already_in_state_and_unparsed(client):
    say_close = say(client, "关窗帘")  # initial curtain is 100 -> real action
    assert say_close["kind"] == "plan"
    assert say(client, "窗帘开到100")["kind"] == "answer"  # already at 100
    unknown = say(client, "把灯弄一下")
    assert unknown["kind"] == "answer"


def test_stop_invalidates_pending_device_command(client):
    rest = confirm(client, say(client, "我想休息")["plan"])
    pending = say(client, "关灯")["plan"]
    client.post(f"/api/services/{rest['service']['serviceId']}/stop", json={"context": ctx()})
    res = client.post(f"/api/plans/{pending['planId']}/confirm", json={"context": ctx(), "planVersion": 1})
    assert res.json()["error"]["code"] == "PLAN_INVALIDATED"


# ---- answers ----


def test_status_query_answers_without_plan_or_writes(client):
    reply = say(client, "卧室现在几度")
    assert reply["kind"] == "answer" and "26°C" in reply["text"] and reply["plan"] is None
    assert devices(client)["version"] == 0


def test_other_topic_gets_scope_answer(client):
    reply = say(client, "今天股市怎么样")
    assert reply["kind"] == "answer" and "休息" in reply["text"]


# ---- memory ----


def memory(client, person):
    return client.get("/api/memory", params={"accountId": "demo-account", "personId": person, "spaceId": SPACE})


def test_memory_shows_own_preference_and_shared_rules(client):
    boot = client.get("/api/bootstrap", params={"accountId": "demo-account"}).json()
    assert all(p["restPreference"] is None for p in boot["persons"])  # no one sees others' preferences
    view = memory(client, "person-chen").json()
    assert view["personId"] == "person-chen" and view["preference"]["acTargetTempC"] == 22
    assert view["editable"] is True and len(view["sharedRules"]) == 3
    assert "15" not in str(view["preference"])  # 林悦's values are not included


def test_preference_update_changes_the_next_plan_only_for_that_person(client):
    res = client.put(
        "/api/memory/preference",
        json={"context": ctx("person-lin"), "preference": {"lightBrightness": 10, "acTargetTempC": 26, "curtainOpenPercent": 0}},
    )
    assert res.status_code == 200 and res.json()["updatedAt"] is not None
    assert [a["value"] for a in say(client, "我想休息")["plan"]["actions"]] == [10, 26.0, 0]
    assert [a["value"] for a in say(client, "我想休息", "person-chen")["plan"]["actions"]] == [30, 22.0, 10]
    items = client.get(f"/api/spaces/{SPACE}/activity", params={"accountId": "demo-account"}).json()["items"]
    assert any(i["kind"] == "memory_updated" and "空调 25°C→26°C" in i["message"] for i in items)


def test_preference_update_limits(client):
    guest = client.put(
        "/api/memory/preference",
        json={"context": ctx("person-guest"), "preference": {"lightBrightness": 10, "acTargetTempC": 26, "curtainOpenPercent": 0}},
    )
    assert guest.status_code == 409 and guest.json()["error"]["code"] == "NOT_EDITABLE"
    bright = client.put(
        "/api/memory/preference",
        json={"context": ctx("person-lin"), "preference": {"lightBrightness": 90, "acTargetTempC": 26, "curtainOpenPercent": 0}},
    )
    assert bright.status_code == 422 and "空间规则" in bright.json()["error"]["message"]
    out_of_range = client.put(
        "/api/memory/preference",
        json={"context": ctx("person-lin"), "preference": {"lightBrightness": 10, "acTargetTempC": 40, "curtainOpenPercent": 0}},
    )
    assert out_of_range.status_code == 422


def test_reset_restores_memory_and_energy_mode(client):
    client.put(
        "/api/memory/preference",
        json={"context": ctx(), "preference": {"lightBrightness": 10, "acTargetTempC": 26, "curtainOpenPercent": 0}},
    )
    energy_mode(client, "eco")
    boot = client.post("/api/demo/reset", params={"accountId": "demo-account"}).json()
    assert boot["spaces"][0]["energyMode"] == "comfort_first"
    assert memory(client, "person-lin").json()["preference"]["acTargetTempC"] == 25


# ---- unit: space execution and energy ----


def test_space_execution_enforces_night_light_rule_and_capabilities():
    agent = SpaceExecutionAgent(seed.NIGHT_LIGHT_MAX)
    ids = iter(range(100))
    new_id = lambda p: f"{p}-{next(ids)}"  # noqa: E731
    actions, notes = agent.rest_actions(
        RestPreference(light_brightness=80, ac_target_temp_c=25, curtain_open_percent=0), CAPABILITIES, new_id
    )
    assert actions[0].value == 60 and "空间规则" in notes[0]
    no_curtain = [c for c in CAPABILITIES if c.device != "curtain"]
    actions, notes = agent.rest_actions(
        RestPreference(light_brightness=20, ac_target_temp_c=25, curtain_open_percent=0), no_curtain, new_id
    )
    assert [a.device for a in actions] == ["light", "ac"] and "curtain" in notes[0]


@pytest.mark.parametrize(
    "text, expect",
    [
        ("把空调调到二十四度", {"ac": 24.0}),
        ("灯调到30%", {"light": 30.0}),
        ("关灯", {"light": 0}),
        ("开灯", {"light": 60.0}),
        ("窗帘开到50", {"curtain": 50.0}),
        ("拉上窗帘", {"curtain": 0}),
    ],
)
def test_command_parser(text, expect):
    t = SpaceExecutionAgent(seed.NIGHT_LIGHT_MAX).parse_command(text)
    got = {k: getattr(t, k) for k in ("light", "ac", "curtain") if getattr(t, k) is not None}
    assert got == expect


def test_energy_rules():
    target = RestPreference(light_brightness=15, ac_target_temp_c=25, curtain_open_percent=0)
    assert comfort_band(target) == (24.0, 26.0)
    assert power_tier(estimate_load_kw(22, 30, 29)) == "medium"
    peak = EnergyIntelligence(29.0, range(18, 23), 8, 20)
    off = EnergyIntelligence(29.0, range(18, 23), 8, 9)
    now = datetime(2026, 9, 17, tzinfo=timezone.utc)
    assert peak.advise(target, "eco", now).applied is True
    assert off.advise(target, "eco", now).applied is False
    cool_outside = EnergyIntelligence(20.0, range(18, 23), 8, 20).advise(target, "eco", now)
    assert cool_outside.applied is False and "不需要制冷" in cool_outside.reason
    edge = RestPreference(light_brightness=15, ac_target_temp_c=30, curtain_open_percent=0)
    assert peak.advise(edge, "eco", now).recommended_ac_c == 30.0  # never above the band / device max


def test_event_adjustment_has_trace_without_energy_change(client):
    confirm(client, say(client, "我想休息")["plan"])
    r = client.post(
        f"/api/spaces/{SPACE}/events", json={"context": ctx(), "type": "room_temperature_changed", "roomTempC": 28}
    ).json()
    agents = [s["agent"] for s in r["plan"]["trace"]]
    assert agents == AGENT_ORDER[:1] + AGENT_ORDER[2:]  # memory is read inside the orchestrator step
    assert "舒适优先" in r["plan"]["trace"][2]["detail"]

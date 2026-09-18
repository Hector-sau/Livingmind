"""T3: the LangGraph path plans the same thing as the legacy path, and checkpoints are real.

The whole suite can also be run through the graph:
    LIVINGMIND_ORCHESTRATOR=langgraph pytest
"""

from __future__ import annotations

import pytest

from app.agents.orchestrator import Orchestrator
from app.contracts import RequestContext
from app.graph.compare import fingerprint_diff, plan_equivalent
from app.graph.runtime import GraphOrchestrator, thread_id
from app.services.rest_service import RestService
from tests.conftest import FakeClock

UTTERANCES = ["我想休息", "我想休息，有点热", "想早点睡，灯再暗一点"]


def _ctx(person: str = "person-lin") -> RequestContext:
    return RequestContext(account_id="demo-account", person_id=person, space_id="space-home-bedroom")


def _graph_service(clock: FakeClock) -> RestService:
    service = RestService(clock=clock)
    service._agent = GraphOrchestrator(service._legacy_agent, lambda space_id: service._devices[space_id])
    return service


def test_both_paths_plan_the_same_thing():
    for person in ("person-lin", "person-chen", "person-guest"):
        for utterance in UTTERANCES:
            legacy = RestService(clock=FakeClock())
            graph = _graph_service(FakeClock())
            a = legacy.create_rest_plan(_ctx(person), utterance)
            b = graph.create_rest_plan(_ctx(person), utterance)
            assert plan_equivalent(a, b), fingerprint_diff(a, b)
            # ids and timestamps are allowed to differ, and do
            assert a.plan_id != b.plan_id or a.created_at == b.created_at


def test_both_paths_answer_the_same_for_commands_and_questions():
    for text in ("把空调调到24度", "关灯", "卧室现在几度", "今天股市怎么样", "把那个弄一下"):
        legacy = RestService(clock=FakeClock())
        graph = _graph_service(FakeClock())
        a = legacy.handle_message(_ctx(), text)
        b = graph.handle_message(_ctx(), text)
        assert (a.kind, a.intent, a.text) == (b.kind, b.intent, b.text)
        assert [s.agent for s in a.trace] == [s.agent for s in b.trace]
        if a.plan is not None:
            assert plan_equivalent(a.plan, b.plan), fingerprint_diff(a.plan, b.plan)


def test_graph_trace_shows_every_node_in_order():
    service = _graph_service(FakeClock())
    plan = service.create_rest_plan(_ctx(), "我想休息")
    assert [step.agent for step in plan.trace] == [
        "orchestrator",
        "memory",
        "experience",
        "energy",
        "space_execution",
        "harness",
    ]
    assert "LangGraph 节点" in plan.trace[0].detail


def test_graph_plans_without_touching_devices():
    service = _graph_service(FakeClock())
    before = service.device_state("demo-account", "space-home-bedroom")
    service.create_rest_plan(_ctx(), "我想休息")
    after = service.device_state("demo-account", "space-home-bedroom")
    assert (after.version, after.light_brightness) == (before.version, before.light_brightness)


def test_checkpoint_records_the_run_and_can_be_read_back():
    service = _graph_service(FakeClock())
    agent: GraphOrchestrator = service._agent  # type: ignore[assignment]
    service.create_rest_plan(_ctx(), "我想休息")
    # the graph names one thread per request; the last one is readable afterwards
    threads = list(agent._saver.list(None))
    assert threads, "no checkpoint was written"
    last = threads[0]
    saved = agent.last_checkpoint(last.config["configurable"]["thread_id"])
    assert saved.values["intent"] == "rest"
    assert saved.values["plan"] is not None
    assert [s.agent for s in saved.values["trace"]][:2] == ["orchestrator", "memory"]
    assert saved.next == ()  # the run finished


def test_thread_id_carries_account_person_space_and_conversation():
    assert thread_id("a", "p", "s", "c") == "account:a:person:p:space:s:conversation:c"


def test_graph_path_still_needs_confirmation_before_devices_change():
    service = _graph_service(FakeClock())
    plan = service.create_rest_plan(_ctx(), "我想休息")
    assert service.device_state("demo-account", "space-home-bedroom").light_brightness == 80
    service.confirm_plan(plan.plan_id, _ctx(), plan.version)
    assert service.device_state("demo-account", "space-home-bedroom").light_brightness == 15


def test_event_adjustments_use_the_legacy_stage_and_say_so():
    service = _graph_service(FakeClock())
    agent: GraphOrchestrator = service._agent  # type: ignore[assignment]
    assert isinstance(agent._legacy, Orchestrator)
    plan = service.create_rest_plan(_ctx(), "我想休息")
    service.confirm_plan(plan.plan_id, _ctx(), plan.version)
    result = service.inject_event("space-home-bedroom", _ctx(), "room_temperature_changed", 30)
    assert result.outcome == "adjusted"
    assert [s.agent for s in result.plan.trace][0] == "orchestrator"

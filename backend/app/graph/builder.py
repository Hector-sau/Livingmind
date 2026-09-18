"""The planning graph.

Nodes call the *same* Orchestrator stage methods as the legacy path — no business rule is
copied here. The graph only expresses routing, order and state, which is what makes the
node trace and the checkpoints real rather than decorative.

Device execution is deliberately outside the graph: it stays in RestService + Harness +
Executor, behind the user's confirmation.
"""

from __future__ import annotations

from typing import Callable

from langgraph.graph import END, START, StateGraph

from app.adapters.protocol import DeviceAdapter
from app.agents.orchestrator.agent import INTENT_LABEL, Orchestrator, _Trace, route_intent
from app.graph.state import LivingMindState

AdapterFor = Callable[[str], DeviceAdapter]
NewId = Callable[[str], str]


def build_graph(orchestrator: Orchestrator, adapter_for: AdapterFor, new_id: NewId):
    """Compile-ready StateGraph. Dependencies are captured here, never put into state."""

    def _trace() -> _Trace:
        return _Trace()

    def route(state: LivingMindState) -> LivingMindState:
        trace = _trace()
        import time

        t0 = time.monotonic()
        forced = state.get("forced_intent")
        intent = forced or route_intent(state["utterance"])
        trace.add(
            "orchestrator",
            f"识别意图：{INTENT_LABEL[intent]}",
            "规则路由（关键词）" + ("；由接口指定为休息请求" if forced else "") + " · LangGraph 节点",
            "rule",
            t0,
        )
        return {"intent": intent, "trace": trace.steps}

    def memory_node(state: LivingMindState) -> LivingMindState:
        trace = _trace()
        ctx = orchestrator.stage_memory(trace, state["person_id"], state["space_id"])
        return {"person_context": ctx, "trace": trace.steps}

    def experience_node(state: LivingMindState) -> LivingMindState:
        trace = _trace()
        adapter = adapter_for(state["space_id"])
        exp = orchestrator.stage_experience(
            trace, state["person_context"], state["utterance"], adapter.read_state(), state.get("planner_mode")
        )
        return {"experience": exp, "clarification_question": exp.clarification_question, "trace": trace.steps}

    def clarification_node(state: LivingMindState) -> LivingMindState:
        trace = _trace()
        reply = orchestrator.clarification_reply(trace, state["utterance"], state.get("clarification_question"))
        return {
            "intent": "clarification",
            "answer": reply.text,
            "reply_kind": "clarification",
            "plan": None,
            "trace": trace.steps,
        }

    def energy_node(state: LivingMindState) -> LivingMindState:
        trace = _trace()
        advice, target = orchestrator.stage_energy(trace, state["experience"], state["energy_mode"])
        return {"energy_advice": advice, "experience_target": target, "trace": trace.steps}

    def execution_node(state: LivingMindState) -> LivingMindState:
        trace = _trace()
        actions, schedule, notes = orchestrator.stage_execution(
            trace,
            state["experience_target"],
            state["person_context"],
            adapter_for(state["space_id"]),
            new_id,
            state.get("wake_time", "07:00"),
        )
        return {"device_actions": actions, "night_schedule": schedule, "execution_notes": notes, "trace": trace.steps}

    def harness_node(state: LivingMindState) -> LivingMindState:
        trace = _trace()
        actions, schedule, _problems = orchestrator.stage_harness(
            trace, state["device_actions"], state["night_schedule"], state["experience"]
        )
        return {"device_actions": actions, "night_schedule": schedule, "trace": trace.steps}

    def build_plan_node(state: LivingMindState) -> LivingMindState:
        trace = _trace()
        plan = orchestrator.build_rest_plan(
            trace,
            state["person_id"],
            state["space_id"],
            state["utterance"],
            state["experience"],
            state["energy_advice"],
            state["device_actions"],
            state["night_schedule"],
            state["execution_notes"],
            state.get("wake_time", "07:00"),
            new_id,
        )
        return {"plan": plan, "reply_kind": "plan", "answer": plan.summary, "trace": trace.steps}

    def command_node(state: LivingMindState) -> LivingMindState:
        trace = _trace()
        reply = orchestrator._command(
            trace,
            state["person_id"],
            state["space_id"],
            state["utterance"],
            state.get("planner_mode"),
            adapter_for(state["space_id"]),
            new_id,
        )
        return {"plan": reply.plan, "answer": reply.text, "reply_kind": reply.kind, "trace": trace.steps}

    def status_node(state: LivingMindState) -> LivingMindState:
        trace = _trace()
        reply = orchestrator.status_reply(trace, adapter_for(state["space_id"]))
        return {"answer": reply.text, "reply_kind": "answer", "trace": trace.steps}

    def other_node(state: LivingMindState) -> LivingMindState:
        trace = _trace()
        reply = orchestrator.other_reply(trace)
        return {"answer": reply.text, "reply_kind": "answer", "trace": trace.steps}

    graph = StateGraph(LivingMindState)
    graph.add_node("route", route)
    graph.add_node("memory", memory_node)
    graph.add_node("experience", experience_node)
    graph.add_node("energy", energy_node)
    graph.add_node("space_execution", execution_node)
    graph.add_node("harness", harness_node)
    graph.add_node("build_plan", build_plan_node)
    graph.add_node("device_command", command_node)
    graph.add_node("status", status_node)
    graph.add_node("other", other_node)
    graph.add_node("clarification", clarification_node)

    graph.add_edge(START, "route")
    graph.add_conditional_edges(
        "route",
        lambda state: state["intent"],
        {
            "rest": "memory",
            "device_command": "device_command",
            "status": "status",
            "other": "other",
            "clarification": "clarification",
        },
    )
    graph.add_edge("memory", "experience")
    graph.add_conditional_edges(
        "experience",
        lambda state: "clarification" if state.get("clarification_question") else "energy",
        {"clarification": "clarification", "energy": "energy"},
    )
    graph.add_edge("energy", "space_execution")
    graph.add_edge("space_execution", "harness")
    graph.add_edge("harness", "build_plan")
    for last in ("build_plan", "device_command", "status", "other", "clarification"):
        graph.add_edge(last, END)
    return graph

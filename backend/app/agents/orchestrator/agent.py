from __future__ import annotations

import re
import time
from datetime import datetime
from typing import Callable, Literal, Optional

from app.adapters.protocol import DeviceAdapter
from app.agents.space_execution import SpaceExecutionAgent
from app.contracts import (
    AgentName,
    AgentStep,
    AssistantReply,
    EnergyMode,
    Plan,
    PlanGeneration,
    PlannerMode,
    StepSource,
    WakeTime,
)
from app.energy import EnergyIntelligence
from app.energy.rules import TIER_LABEL
from app.harness.policy import precheck
from app.memory import MemoryService
from app.observability.events import record
from app.rules.rest_rule import PLAN_TTL
from app.services.planner import ExperienceOutcome, Planner

Intent = Literal["rest", "device_command", "status", "other", "clarification"]
NewId = Callable[[str], str]

_REST = re.compile(r"休息|睡|躺|困|累|午睡|歇|放松|安静")
_DEVICE = re.compile(r"灯|空调|窗帘")
_ACTION = re.compile(r"开|关|调|设|拉|合|到")
_STATUS = re.compile(r"现在|状态|多少|几度|怎么样了|情况")
_NEGATED_REST = re.compile(r"(?:不想|不要|不用|别).{0,4}(?:休息|睡|躺|午睡|歇)")
_VAGUE_ACTION = re.compile(r"(?:那个|这个|它).{0,5}(?:调|开|关|弄)|(?:调高|调低)(?:一点)?$|(?:大一点|小一点|亮一点|暗一点)$")


def clarification_question(text: str) -> str:
    """A deterministic question for requests that must not become device actions yet."""
    t = text.replace(" ", "")
    if "灯" in t and re.search(r"开灯.*关灯|关灯.*开灯", t):
        return "你希望灯最终打开还是关闭？"
    return "请说明要调整灯、空调还是窗帘，并告诉我目标值，例如“灯调到 20%”。"


def route_intent(text: str) -> Intent:
    """Rule router (deterministic, labelled 'rule' in the trace)."""
    t = text.replace(" ", "")
    explicit_device_action = bool(_DEVICE.search(t) and _ACTION.search(t))
    if "灯" in t and re.search(r"开灯.*关灯|关灯.*开灯", t):
        return "clarification"
    if explicit_device_action and _NEGATED_REST.search(t):
        return "device_command"
    if _REST.search(t) and not _NEGATED_REST.search(t):
        return "rest"
    if _STATUS.search(t) and (_DEVICE.search(t) or "房间" in t or "卧室" in t or "温度" in t):
        if re.search(r"多少|几度|怎么样了|状态|情况", t):
            return "status"
    if explicit_device_action:
        return "device_command"
    if _STATUS.search(t) and (_DEVICE.search(t) or "房间" in t or "卧室" in t or "温度" in t):
        return "status"
    if _VAGUE_ACTION.search(t):
        return "clarification"
    return "other"


INTENT_LABEL = {
    "rest": "休息请求",
    "device_command": "设备指令",
    "status": "状态查询",
    "other": "其他话题",
    "clarification": "需要澄清",
}


class _Trace:
    def __init__(self) -> None:
        self.steps: list[AgentStep] = []

    def add(self, agent: AgentName, title: str, detail: str, source: StepSource, started: float, ok: bool = True) -> None:
        elapsed_ms = (time.monotonic() - started) * 1000
        self.steps.append(
            AgentStep(
                agent=agent,
                title=title,
                detail=detail,
                source=source,
                latency_ms=int(elapsed_ms),
                ok=ok,
            )
        )
        record("agent.stage", agent=agent, source=source, ok=ok, durationMs=round(elapsed_ms, 3))


class Orchestrator:
    """Rule router plus the stages. The LangGraph path (app/graph) calls the same methods."""

    def __init__(
        self,
        planner: Planner,
        memory: MemoryService,
        energy: EnergyIntelligence,
        space_execution: SpaceExecutionAgent,
        clock: Callable[[], datetime],
    ):
        self.planner = planner
        self.memory = memory
        self.energy = energy
        self.space = space_execution
        self._clock = clock

    # ---- entry point ----

    def handle(
        self,
        person_id: str,
        space_id: str,
        text: str,
        mode: Optional[PlannerMode],
        adapter: DeviceAdapter,
        energy_mode: EnergyMode,
        new_id: NewId,
        force_intent: Optional[Intent] = None,
        wake_time: WakeTime = "07:00",
    ) -> AssistantReply:
        trace = _Trace()
        t0 = time.monotonic()
        intent: Intent = force_intent or route_intent(text)
        trace.add(
            "orchestrator",
            f"识别意图：{INTENT_LABEL[intent]}",
            "规则路由（关键词）" + ("；由接口指定为休息请求" if force_intent else ""),
            "rule",
            t0,
        )
        if intent == "rest":
            return self._rest(trace, person_id, space_id, text, mode, adapter, energy_mode, new_id, wake_time)
        if intent == "device_command":
            return self._command(trace, person_id, space_id, text, mode, adapter, new_id)
        if intent == "status":
            return self.status_reply(trace, adapter)
        if intent == "clarification":
            return self.clarification_reply(trace, text)
        return self.other_reply(trace)

    def clarification_reply(self, trace, text: str, question: Optional[str] = None) -> AssistantReply:
        t = time.monotonic()
        prompt = question or clarification_question(text)
        trace.add("orchestrator", "请求澄清", "没有生成计划或设备动作", "rule", t)
        return AssistantReply(kind="clarification", intent="clarification", text=prompt, plan=None, trace=trace.steps)

    def status_reply(self, trace, adapter: DeviceAdapter) -> AssistantReply:
        state = adapter.read_state()
        t = time.monotonic()
        answer = (
            f"卧室现在：灯光 {state.light_brightness}%，空调设定 {state.ac_target_temp_c:g}°C，"
            f"窗帘开度 {state.curtain_open_percent}%（虚拟设备读数）。"
        )
        trace.add("space_execution", "读取设备状态", "只读，不生成动作", "rule", t)
        return AssistantReply(kind="answer", intent="status", text=answer, plan=None, trace=trace.steps)

    def other_reply(self, trace) -> AssistantReply:
        answer = "我目前负责休息相关的空间服务：可以说“我想休息”，或者直接说“把灯关了”“空调调到 24 度”。"
        return AssistantReply(kind="answer", intent="other", text=answer, plan=None, trace=trace.steps)

    # ---- full branch: memory -> experience -> energy -> space execution -> harness ----

    def _rest(self, trace, person_id, space_id, text, mode, adapter, energy_mode, new_id, wake_time: WakeTime) -> AssistantReply:
        """Legacy sequential composition of the same stages the graph nodes call."""
        ctx = self.stage_memory(trace, person_id, space_id)
        state = adapter.read_state()
        exp = self.stage_experience(trace, ctx, text, state, mode)
        if exp.clarification_question:
            return self.clarification_reply(trace, text, exp.clarification_question)
        advice, target = self.stage_energy(trace, exp, energy_mode)
        actions, schedule, exec_notes = self.stage_execution(trace, target, ctx, adapter, new_id, wake_time)
        actions, schedule, problems = self.stage_harness(trace, actions, schedule, exp)
        plan = self.build_rest_plan(
            trace, person_id, space_id, text, exp, advice, actions, schedule, exec_notes, wake_time, new_id
        )
        return AssistantReply(kind="plan", intent="rest", text=exp.summary, plan=plan, trace=trace.steps)

    # ---- stages: one per graph node, shared by both orchestration paths ----

    def stage_memory(self, trace, person_id: str, space_id: str):
        t = time.monotonic()
        ctx = self.memory.context_for(person_id, space_id)
        who = "访客（空间默认设置）" if ctx.person.is_guest else f"{ctx.person.name} 的休息偏好（仅本人）"
        trace.add("memory", "读取上下文", f"{who} + 空间规则 {len(ctx.shared_rules)} 条", "rule", t)
        return ctx

    def stage_experience(self, trace, ctx, text: str, state, mode) -> ExperienceOutcome:
        t = time.monotonic()
        exp: ExperienceOutcome = self.planner.plan(ctx.person, text, state, mode)
        s = exp.settings
        exp_detail = f"体验目标：灯光 {s.light_brightness}% · 空调 {s.ac_target_temp_c:g}°C · 窗帘 {s.curtain_open_percent}%"
        if exp.fallback_reason:
            exp_detail += f"；模型未采用：{exp.fallback_reason}"
        trace.add("experience", "生成体验目标", exp_detail, exp.source, t, ok=exp.fallback_reason is None)
        return exp

    def stage_energy(self, trace, exp: ExperienceOutcome, energy_mode):
        s = exp.settings
        t = time.monotonic()
        advice = self.energy.advise(s, energy_mode, self._clock())
        target = s.model_copy(update={"ac_target_temp_c": advice.recommended_ac_c}) if advice.applied else s
        energy_detail = (
            f"{'节能模式' if energy_mode == 'eco' else '舒适优先'} · "
            f"{'高峰' if advice.tariff == 'peak' else '非高峰'}电价 · "
            f"建议 {advice.recommended_ac_c:g}°C（舒适范围 {advice.comfort_min_c:g}–{advice.comfort_max_c:g}°C）"
            f"{' · 已应用' if advice.applied else ' · 未改设定'}"
            f" · 估算负荷 {advice.load_kw_before:g}→{advice.load_kw_after:g} kW（{TIER_LABEL[advice.tier_after]}档）"
        )
        trace.add("energy", "能源策略", energy_detail, "rule", t)
        return advice, target

    def stage_execution(self, trace, target, ctx, adapter, new_id, wake_time: WakeTime):
        t = time.monotonic()
        caps = adapter.list_capabilities()
        actions, exec_notes = self.space.rest_actions(target, caps, new_id)
        schedule = self.space.night_schedule(target, ctx.preference, caps, new_id, wake_time)
        trace.add(
            "space_execution",
            "生成设备动作",
            f"能力 {len(caps)} 项 · 生成 {len(actions)} 个动作 · 整晚安排 {len(schedule)} 个定时步骤"
            + (f" · {'；'.join(exec_notes)}" if exec_notes else ""),
            "rule",
            t,
        )
        return actions, schedule, exec_notes

    def stage_harness(self, trace, actions, schedule, exp: ExperienceOutcome):
        t = time.monotonic()
        actions, problems = precheck(actions)
        for step in schedule:
            step.actions, step_problems = precheck(step.actions)
            problems += [f"{step.at} {p}" for p in step_problems]
        model_calls = 1 if exp.generation.mode_requested == "model" and exp.generation.provider else 0
        trace.add(
            "harness",
            "执行前检查",
            ("全部通过白名单与参数范围" if not problems else f"拦截 {len(problems)} 个动作：{'；'.join(problems)}")
            + f" · 本次模型调用 {model_calls}/1 · 计划与整晚安排需用户确认后执行",
            "rule",
            t,
            ok=not problems,
        )
        return actions, schedule, problems

    def build_rest_plan(
        self, trace, person_id, space_id, text, exp: ExperienceOutcome, advice, actions, schedule, exec_notes,
        wake_time, new_id: NewId,
    ) -> Plan:
        notes = list(exp.notes) + exec_notes
        if advice.applied:
            notes.append(
                f"节能模式：空调由 {advice.requested_ac_c:g}°C 调到 {advice.recommended_ac_c:g}°C（仍在舒适范围内）"
            )
        if schedule:
            notes.append(
                f"整晚安排（模拟时钟，随计划一起确认）：{schedule[0].at} 起共 {len(schedule)} 步，{schedule[-1].at} 唤醒完成后服务结束"
            )
        now = self._clock()
        plan = Plan(
            plan_id=new_id("plan"),
            version=1,
            person_id=person_id,
            space_id=space_id,
            scenario="rest",
            source=exp.source,
            summary=exp.summary,
            notes=notes,
            utterance=text,
            actions=actions,
            status="proposed",
            created_at=now,
            expires_at=now + PLAN_TTL,
            generation=exp.generation,
            trace=trace.steps,
            energy=advice,
            schedule=schedule,
            wake_time=wake_time,
        )
        record("plan.ready", planId=plan.plan_id, source=plan.source,
               actionIds=[action.action_id for action in actions])
        return plan

    # ---- simplified branch: direct device command ----

    def _command(self, trace, person_id, space_id, text, mode, adapter, new_id) -> AssistantReply:
        state = adapter.read_state()
        t = time.monotonic()
        target = self.space.parse_command(text)
        if target.empty():
            trace.add("space_execution", "解析设备指令", "没有识别出设备和目标值", "rule", t, ok=False)
            return AssistantReply(
                kind="answer",
                intent="device_command",
                text="我没听清要调哪个设备，可以说“把灯关了”“空调调到 24 度”或“打开窗帘”。",
                plan=None,
                trace=trace.steps,
            )
        actions, notes = self.space.command_actions(target, state, new_id)
        trace.add("space_execution", "解析设备指令", f"{'、'.join(target.phrases)} → {len(actions)} 个动作", "rule", t)

        t = time.monotonic()
        actions, problems = precheck(actions)
        trace.add(
            "harness",
            "执行前检查",
            ("通过白名单与参数范围" if not problems else f"拦截：{'；'.join(problems)}") + " · 需用户确认后执行",
            "rule",
            t,
            ok=not problems,
        )
        if not actions:
            why = "；".join(problems + notes) or "没有需要执行的动作"
            return AssistantReply(kind="answer", intent="device_command", text=f"没有生成动作：{why}", plan=None, trace=trace.steps)

        now = self._clock()
        summary = "设备指令：" + "，".join(a.label for a in actions)
        plan = Plan(
            plan_id=new_id("plan"),
            version=1,
            person_id=person_id,
            space_id=space_id,
            scenario="device_command",
            source="rule",
            summary=summary,
            notes=["简化分支：直接设备指令，不经过体验 Agent 与能源模块"] + notes + [f"拦截：{p}" for p in problems],
            utterance=text,
            actions=actions,
            status="proposed",
            created_at=now,
            expires_at=now + PLAN_TTL,
            generation=PlanGeneration(
                mode_requested=mode or self.planner.default_mode,
                provider=None,
                model=None,
                latency_ms=0,
                fallback_reason=None,
                goal=None,
            ),
            trace=trace.steps,
            energy=None,
            schedule=[],
        )
        return AssistantReply(kind="plan", intent="device_command", text=summary, plan=plan, trace=trace.steps)

    # ---- event adjustment: experience -> space execution -> harness (comfort first, no energy) ----

    def adjustment_plan(
        self,
        person_id: str,
        space_id: str,
        room_temp_c: float,
        mode: PlannerMode,
        adapter: DeviceAdapter,
        new_id: NewId,
    ) -> tuple[Plan, Optional[str]]:
        trace = _Trace()
        t = time.monotonic()
        ctx = self.memory.context_for(person_id, space_id)
        trace.add("orchestrator", "处理模拟事件", f"室温 {room_temp_c:g}°C · 读取{ctx.person.name}的偏好", "rule", t)
        state = adapter.read_state()
        t = time.monotonic()
        exp = self.planner.plan_adjustment(ctx.person, room_temp_c, state, mode)
        trace.add("experience", "调整目标", exp.summary, exp.source, t, ok=exp.fallback_reason is None)
        t = time.monotonic()
        trace.add("energy", "能源策略", "事件调整以舒适优先，不应用节能策略", "rule", t)
        t = time.monotonic()
        actions = self.space.adjustment_actions(exp.settings, state, adapter.list_capabilities(), new_id)
        trace.add("space_execution", "生成调整动作", f"只对有变化的设备生成 {len(actions)} 个动作", "rule", t)
        t = time.monotonic()
        actions, problems = precheck(actions)
        trace.add("harness", "执行前检查", "通过" if not problems else "；".join(problems), "rule", t, ok=not problems)
        now = self._clock()
        plan = Plan(
            plan_id=new_id("plan"),
            version=1,
            person_id=person_id,
            space_id=space_id,
            scenario="rest_adjustment",
            source=exp.source,
            summary=exp.summary,
            notes=exp.notes,
            utterance=f"【模拟事件】室温 {room_temp_c:g}°C",
            actions=actions,
            status="proposed",
            created_at=now,
            expires_at=now + PLAN_TTL,
            generation=exp.generation,
            trace=trace.steps,
            energy=None,
            schedule=[],
        )
        return plan, exp.fallback_reason

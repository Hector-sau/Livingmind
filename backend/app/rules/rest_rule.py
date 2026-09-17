"""Fixed rest rule (no model) and the shared action builder used by both rule and model plans."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Callable

from app.contracts import DeviceAction, Person, Plan, PlanGeneration, PlanSource, RestPreference

PLAN_TTL = timedelta(minutes=10)


def actions_from_settings(settings: RestPreference, new_id: Callable[[str], str]) -> list[DeviceAction]:
    """Map target settings to device actions. Same mapping for rule and model plans."""
    curtain_label = "窗帘全部关闭" if settings.curtain_open_percent == 0 else f"窗帘保留 {settings.curtain_open_percent}%"
    return [
        DeviceAction(
            action_id=new_id("act"),
            device="light",
            command="set_brightness",
            value=settings.light_brightness,
            label=f"灯光亮度调到 {settings.light_brightness}%",
        ),
        DeviceAction(
            action_id=new_id("act"),
            device="ac",
            command="set_target_temperature",
            value=settings.ac_target_temp_c,
            label=f"空调设定 {settings.ac_target_temp_c:g}°C",
        ),
        DeviceAction(
            action_id=new_id("act"),
            device="curtain",
            command="set_open_percent",
            value=settings.curtain_open_percent,
            label=curtain_label,
        ),
    ]


def build_plan(
    *,
    person: Person,
    space_id: str,
    utterance: str,
    now: datetime,
    new_id: Callable[[str], str],
    settings: RestPreference,
    source: PlanSource,
    summary: str,
    notes: list[str],
    generation: PlanGeneration,
) -> Plan:
    return Plan(
        plan_id=new_id("plan"),
        version=1,
        person_id=person.person_id,
        space_id=space_id,
        scenario="rest",
        source=source,
        summary=summary,
        notes=notes,
        utterance=utterance,
        actions=actions_from_settings(settings, new_id),
        status="proposed",
        created_at=now,
        expires_at=now + PLAN_TTL,
        generation=generation,
    )


def build_rest_plan(
    person: Person,
    space_id: str,
    utterance: str,
    now: datetime,
    new_id: Callable[[str], str],
    *,
    latency_ms: int = 0,
    fallback_reason: str | None = None,
) -> Plan:
    """Rule plan straight from the seeded preference. With fallback_reason it is a rule fallback."""
    is_fallback = fallback_reason is not None
    notes = [
        "规则计划：由后端固定休息规则生成，没有调用模型"
        if not is_fallback
        else f"规则降级：请求了模型，但改用固定规则生成（{fallback_reason}）",
        "当前为固定休息场景，输入文字只做记录，不做语义理解",
    ]
    return build_plan(
        person=person,
        space_id=space_id,
        utterance=utterance,
        now=now,
        new_id=new_id,
        settings=person.rest_preference,
        source="rule_fallback" if is_fallback else "rule",
        summary=f"按 {person.name} 的休息偏好调整灯光、空调和窗帘",
        notes=notes,
        generation=PlanGeneration(
            mode_requested="model" if is_fallback else "rule",
            provider=None,
            model=None,
            latency_ms=latency_ms,
            fallback_reason=fallback_reason,
            goal=None,
        ),
    )

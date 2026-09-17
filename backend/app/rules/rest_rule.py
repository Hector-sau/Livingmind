"""Fixed rest rule (no model) and the shared action builder used by both rule and model plans."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Callable

from typing import Literal, Optional

from app.contracts import DeviceAction, DeviceState, Person, Plan, PlanGeneration, PlanSource, RestPreference

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


def changed_actions(settings: RestPreference, state: DeviceState, new_id: Callable[[str], str]) -> list[DeviceAction]:
    """Only the actions whose target differs from the current device state (used by adjustments)."""
    current = {
        "light": state.light_brightness,
        "ac": state.ac_target_temp_c,
        "curtain": state.curtain_open_percent,
    }
    return [a for a in actions_from_settings(settings, new_id) if float(a.value) != float(current[a.device])]


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
    scenario: Literal["rest", "rest_adjustment"] = "rest",
    actions: Optional[list[DeviceAction]] = None,
) -> Plan:
    return Plan(
        plan_id=new_id("plan"),
        version=1,
        person_id=person.person_id,
        space_id=space_id,
        scenario=scenario,
        source=source,
        summary=summary,
        notes=notes,
        utterance=utterance,
        actions=actions if actions is not None else actions_from_settings(settings, new_id),
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
    if person.is_guest:
        notes.insert(0, "访客模式：使用空间默认设置，没有读取任何个人偏好")
    summary = (
        "按空间默认设置调整灯光、空调和窗帘（访客）"
        if person.is_guest
        else f"按 {person.name} 的休息偏好调整灯光、空调和窗帘"
    )
    return build_plan(
        person=person,
        space_id=space_id,
        utterance=utterance,
        now=now,
        new_id=new_id,
        settings=person.rest_preference,
        source="rule_fallback" if is_fallback else "rule",
        summary=summary,
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


# ---- adjustment rule (step 6) ----

ADJUST_TRIGGER_C = 2.0  # react when the room is this far from the AC set point
ADJUST_STEP_C = 1.0
ADJUST_BAND_C = 3.0  # never move more than this away from the person's preference


def adjustment_rule(pref: RestPreference, state: DeviceState, room_temp_c: float) -> tuple[RestPreference, str]:
    """Rule for one adjustment after a room-temperature event. Only the AC set point changes."""
    target = state.ac_target_temp_c
    new = target
    if room_temp_c >= target + ADJUST_TRIGGER_C:
        new = max(target - ADJUST_STEP_C, pref.ac_target_temp_c - ADJUST_BAND_C, 16.0)
        why = f"室温 {room_temp_c:g}°C 高于设定 {target:g}°C"
    elif room_temp_c <= target - ADJUST_TRIGGER_C:
        new = min(target + ADJUST_STEP_C, pref.ac_target_temp_c + ADJUST_BAND_C, 30.0)
        why = f"室温 {room_temp_c:g}°C 低于设定 {target:g}°C"
    else:
        why = f"室温 {room_temp_c:g}°C 与设定 {target:g}°C 接近"
    settings = RestPreference(
        light_brightness=state.light_brightness,
        ac_target_temp_c=new,
        curtain_open_percent=state.curtain_open_percent,
    )
    if new == target:
        summary = f"{why}，无需调整" if "接近" in why else f"{why}，但已到偏好允许的调整边界"
    else:
        summary = f"{why}，空调调整到 {new:g}°C"
    return settings, summary


def build_adjustment_rule_plan(
    person: Person,
    space_id: str,
    room_temp_c: float,
    state: DeviceState,
    now: datetime,
    new_id: Callable[[str], str],
    *,
    latency_ms: int = 0,
    fallback_reason: Optional[str] = None,
) -> Plan:
    settings, summary = adjustment_rule(person.rest_preference, state, room_temp_c)
    is_fallback = fallback_reason is not None
    return build_plan(
        person=person,
        space_id=space_id,
        utterance=f"【模拟事件】室温 {room_temp_c:g}°C",
        now=now,
        new_id=new_id,
        settings=settings,
        source="rule_fallback" if is_fallback else "rule",
        summary=summary,
        notes=[
            "规则调整：室温偏离设定 2°C 以上时，空调每次调整 1°C，且不超出偏好 ±3°C"
            if not is_fallback
            else f"规则降级：请求了模型，但改用调整规则（{fallback_reason}）",
        ],
        generation=PlanGeneration(
            mode_requested="model" if is_fallback else "rule",
            provider=None,
            model=None,
            latency_ms=latency_ms,
            fallback_reason=fallback_reason,
            goal=None,
        ),
        scenario="rest_adjustment",
        actions=changed_actions(settings, state, new_id),
    )

"""Fixed rest rule (no model). Plan values come straight from the person's seeded preference."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Callable

from app.contracts import DeviceAction, Person, Plan

PLAN_TTL = timedelta(minutes=10)


def build_rest_plan(person: Person, space_id: str, utterance: str, now: datetime, new_id: Callable[[str], str]) -> Plan:
    pref = person.rest_preference
    curtain_label = "窗帘全部关闭" if pref.curtain_open_percent == 0 else f"窗帘保留 {pref.curtain_open_percent}%"
    actions = [
        DeviceAction(
            action_id=new_id("act"),
            device="light",
            command="set_brightness",
            value=pref.light_brightness,
            label=f"灯光亮度调到 {pref.light_brightness}%",
        ),
        DeviceAction(
            action_id=new_id("act"),
            device="ac",
            command="set_target_temperature",
            value=pref.ac_target_temp_c,
            label=f"空调设定 {pref.ac_target_temp_c:g}°C",
        ),
        DeviceAction(
            action_id=new_id("act"),
            device="curtain",
            command="set_open_percent",
            value=pref.curtain_open_percent,
            label=curtain_label,
        ),
    ]
    return Plan(
        plan_id=new_id("plan"),
        version=1,
        person_id=person.person_id,
        space_id=space_id,
        scenario="rest",
        source="rule",
        summary=f"按 {person.name} 的休息偏好调整灯光、空调和窗帘",
        notes=[
            "规则计划：由后端固定休息规则生成，没有调用模型",
            "当前为固定休息场景，输入文字只做记录，不做语义理解",
        ],
        utterance=utterance,
        actions=actions,
        status="proposed",
        created_at=now,
        expires_at=now + PLAN_TTL,
    )

"""Overnight schedule rule (step 7, no model).

The night runs on a simulated clock that starts at NIGHT_START_LOCAL. Nothing here reads the
wall clock; the demo advances the clock explicitly, so every step is reproducible.
Front-end mock (apps/mobile/services/mock/agents.ts::nightPlan) mirrors this table.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.contracts import RestPreference, WakeTime
from app.demo import seed
from app.rules.rest_rule import ADJUST_BAND_C


def _minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


START_MIN = _minutes(seed.NIGHT_START_LOCAL)


def offset_of(hhmm: str) -> int:
    return (_minutes(hhmm) - START_MIN) % (24 * 60)


def clock_label(offset_min: int) -> str:
    total = (START_MIN + offset_min) % (24 * 60)
    return f"{total // 60:02d}:{total % 60:02d}"


@dataclass(frozen=True)
class StepSpec:
    phase: str
    at: str
    offset_min: int
    title: str
    targets: tuple[tuple[str, float], ...]


def _at(hhmm: str) -> tuple[str, int]:
    return hhmm, offset_of(hhmm)


def night_plan(
    target: RestPreference, preference: RestPreference, night_light_max: int, wake_time: WakeTime = seed.WAKE_TIME_LOCAL
) -> list[StepSpec]:
    """Five timed steps: sleep, deep night, and a three-step wake-up ending at the requested demo wake time."""
    ac = target.ac_target_temp_c
    deep_ac = min(ac + seed.DEEP_NIGHT_AC_RAISE_C, preference.ac_target_temp_c + ADJUST_BAND_C, 30.0)
    wake_light = min(seed.WAKE_LIGHT_MAX, night_light_max)
    wake_min = offset_of(wake_time)
    curtain = target.curtain_open_percent

    deep_title = f"深夜：空调调高到 {deep_ac:g}°C" if deep_ac != ac else f"深夜：空调保持 {ac:g}°C（已到偏好边界）"
    specs = [
        (*_at("23:00"), "sleep", "入睡：关灯", (("light", 0),)),
        (*_at("01:00"), "deep", deep_title, (("ac", deep_ac),)),
        (clock_label(wake_min - 30), wake_min - 30, "wake", "唤醒 1/3：窗帘微开、灯光 20%",
         (("curtain", max(curtain, 30)), ("light", 20))),
        (clock_label(wake_min - 15), wake_min - 15, "wake", f"唤醒 2/3：窗帘 60%、灯光 40%、空调回到 {ac:g}°C",
         (("curtain", max(curtain, 60)), ("light", 40), ("ac", ac))),
        (clock_label(wake_min), wake_min, "wake", f"唤醒 3/3：窗帘全开、灯光 {wake_light}%",
         (("curtain", 100), ("light", wake_light))),
    ]
    return [StepSpec(phase=ph, at=at, offset_min=off, title=title, targets=tg) for at, off, ph, title, tg in specs]

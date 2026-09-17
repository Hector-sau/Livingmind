from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Optional

from app.contracts import Capability, DeviceAction, DeviceState, RestPreference
from app.rules.rest_rule import actions_from_settings

NewId = Callable[[str], str]

_CN_NUM = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}


def _number(text: str) -> Optional[float]:
    m = re.search(r"(\d+(?:\.\d+)?)", text)
    if m:
        return float(m.group(1))
    m = re.search(r"([二两三四五六七八九]?十[一二三四五六七八九]?)", text)
    if m:
        s = m.group(1)
        tens = _CN_NUM.get(s[0], 1) if s[0] != "十" else 1
        ones = _CN_NUM.get(s[-1], 0) if s[-1] != "十" else 0
        return float(tens * 10 + ones)
    return None


@dataclass
class CommandTarget:
    """Partial device targets parsed from a direct command."""

    light: Optional[float] = None
    ac: Optional[float] = None
    curtain: Optional[float] = None
    phrases: list[str] = field(default_factory=list)

    def empty(self) -> bool:
        return self.light is None and self.ac is None and self.curtain is None


LABELS = {
    "light": lambda v: f"灯光亮度调到 {v:g}%",
    "ac": lambda v: f"空调设定 {v:g}°C",
    "curtain": lambda v: "窗帘全部关闭" if v == 0 else f"窗帘开到 {v:g}%",
}
COMMANDS = {"light": "set_brightness", "ac": "set_target_temperature", "curtain": "set_open_percent"}


class SpaceExecutionAgent:
    def __init__(self, night_light_max: int):
        self._night_light_max = night_light_max

    # ---- capability awareness ----

    @staticmethod
    def supported(capabilities: list[Capability]) -> set[str]:
        return {c.device for c in capabilities}

    # ---- experience target -> actions ----

    def rest_actions(
        self, target: RestPreference, capabilities: list[Capability], new_id: NewId
    ) -> tuple[list[DeviceAction], list[str]]:
        notes: list[str] = []
        if target.light_brightness > self._night_light_max:
            notes.append(f"空间规则：休息时灯光不超过 {self._night_light_max}%，已从 {target.light_brightness}% 调整")
            target = target.model_copy(update={"light_brightness": self._night_light_max})
        supported = self.supported(capabilities)
        actions = [a for a in actions_from_settings(target, new_id) if a.device in supported]
        missing = {"light", "ac", "curtain"} - supported
        if missing:
            notes.append(f"空间缺少设备能力：{', '.join(sorted(missing))}，相应动作已跳过")
        return actions, notes

    def adjustment_actions(
        self, target: RestPreference, state: DeviceState, capabilities: list[Capability], new_id: NewId
    ) -> list[DeviceAction]:
        current = {"light": state.light_brightness, "ac": state.ac_target_temp_c, "curtain": state.curtain_open_percent}
        actions, _ = self.rest_actions(target, capabilities, new_id)
        return [a for a in actions if float(a.value) != float(current[a.device])]

    # ---- direct device commands (simplified branch, rule parser) ----

    def parse_command(self, text: str) -> CommandTarget:
        t = text.replace(" ", "")
        out = CommandTarget()
        # light
        if re.search(r"关灯|灯关|熄灯|把灯关", t):
            out.light = 0
            out.phrases.append("关灯")
        elif re.search(r"灯", t) and re.search(r"调到|开到|设到|调成|亮度", t) and _number(t.split("灯", 1)[1]) is not None:
            out.light = _number(t.split("灯", 1)[1])
            out.phrases.append("调灯光")
        elif re.search(r"开灯|打开灯|把灯打开", t):
            out.light = float(self._night_light_max)
            out.phrases.append("开灯")
        # air conditioner
        if "空调" in t:
            n = _number(t.split("空调", 1)[1])
            if n is not None:
                out.ac = n
                out.phrases.append("调空调")
        # curtain
        if "窗帘" in t:
            rest = t.split("窗帘", 1)[1]
            n = _number(rest)
            if n is not None and re.search(r"开到|调到|留", rest):
                out.curtain = n
                out.phrases.append("调窗帘")
            elif re.search(r"关|拉上|合上", t):
                out.curtain = 0
                out.phrases.append("关窗帘")
            elif re.search(r"打开|拉开|开", t):
                out.curtain = 100
                out.phrases.append("开窗帘")
        return out

    def command_actions(self, target: CommandTarget, state: DeviceState, new_id: NewId) -> tuple[list[DeviceAction], list[str]]:
        current = {"light": state.light_brightness, "ac": state.ac_target_temp_c, "curtain": state.curtain_open_percent}
        actions, notes = [], []
        for device in ("light", "ac", "curtain"):
            value = getattr(target, device)
            if value is None:
                continue
            if float(value) == float(current[device]):
                notes.append(f"{LABELS[device](value)}：已经是这个状态")
                continue
            actions.append(
                DeviceAction(
                    action_id=new_id("act"),
                    device=device,  # type: ignore[arg-type]
                    command=COMMANDS[device],  # type: ignore[arg-type]
                    value=value,
                    label=LABELS[device](value),
                )
            )
        return actions, notes

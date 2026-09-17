from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Optional

from pydantic import ValidationError

from app.agents.experience.provider import ChatProvider, ProviderError
from app.agents.experience.schema import OUTPUT_FORMAT_HINT, ExperienceOutput
from app.contracts import DeviceState, Person

SYSTEM_PROMPT = f"""你是 LivingMind 的 Experience Agent，负责把一个人的生活需求转化为卧室的休息体验目标。
你只能提出设置建议；设备由另一个受控执行器在用户确认后操作，所以不要假设你已经改变了任何设备。

规则：
1. 以这个人已授权的休息偏好为基线；只有当用户这句话明确表达了不同需要（例如更暗、更凉、想留缝透气）时才偏离，并在 rationale 里说明。
   偏离幅度上限：灯光与窗帘各 ±40，空调 ±3°C；超出上限的建议会被系统拒绝。
2. 数值必须在范围内：light_brightness 0-100 整数，ac_target_temp_c 16-30，curtain_open_percent 0-100 整数。
3. 如果这句话与休息无关或无法理解，仍然给出基于偏好的休息设置，并把 needs_clarification 设为 true、写一个简短的 clarification_question。
4. 只输出一个 JSON 对象，不要任何其他文字。格式：
{OUTPUT_FORMAT_HINT}"""


@dataclass
class ExperienceResult:
    output: ExperienceOutput
    provider: str
    model: str
    latency_ms: int


class ExperienceError(Exception):
    """Any reason the model path could not produce a valid plan. Callers fall back to rules."""

    def __init__(self, kind: str, message: str, latency_ms: int):
        super().__init__(message)
        self.kind = kind
        self.message = message
        self.latency_ms = latency_ms


def build_user_prompt(person: Person, device_state: DeviceState, utterance: str) -> str:
    pref = person.rest_preference
    return (
        f"人物：{person.name}（{person.description}）\n"
        f"已授权的休息偏好：灯光 {pref.light_brightness}%，空调 {pref.ac_target_temp_c:g}°C，"
        f"窗帘开度 {pref.curtain_open_percent}%\n"
        f"当前设备状态：灯光 {device_state.light_brightness}%，空调 {device_state.ac_target_temp_c:g}°C，"
        f"窗帘开度 {device_state.curtain_open_percent}%\n"
        f"用户这句话：「{utterance.strip()}」"
    )


class ExperienceAgent:
    def __init__(self, provider: ChatProvider, timeout_s: float):
        self._provider = provider
        self._timeout_s = timeout_s

    def plan(self, person: Person, device_state: DeviceState, utterance: str) -> ExperienceResult:
        started = time.monotonic()
        elapsed = lambda: int((time.monotonic() - started) * 1000)  # noqa: E731
        try:
            raw = self._provider.complete_json(SYSTEM_PROMPT, build_user_prompt(person, device_state, utterance), self._timeout_s)
        except ProviderError as exc:
            raise ExperienceError(exc.kind, exc.message, elapsed()) from exc
        try:
            data = json.loads(_strip_code_fence(raw))
        except ValueError as exc:
            raise ExperienceError("parse", "模型输出不是合法 JSON", elapsed()) from exc
        try:
            output = ExperienceOutput.model_validate(data)
        except ValidationError as exc:
            first = exc.errors()[0] if exc.errors() else {}
            field = ".".join(str(x) for x in first.get("loc", ())) or "?"
            raise ExperienceError("schema", f"模型输出不符合结构要求（{field}）", elapsed()) from exc
        return ExperienceResult(output=output, provider=self._provider.name, model=self._provider.model, latency_ms=elapsed())


def _strip_code_fence(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else ""
        if t.rstrip().endswith("```"):
            t = t.rstrip()[:-3]
    return t.strip()

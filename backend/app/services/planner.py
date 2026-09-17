"""Experience stage: produce the experience target (three settings) by rule or by the Experience Agent.

Model failures of any kind (not configured, timeout, network, HTTP, bad JSON, schema, deviation limit)
fall back to rules; the outcome's source is "rule_fallback" with the reason attached.
Nothing here builds device actions or touches devices.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Optional

from app import config
from app.agents.experience import ExperienceAgent, ExperienceError
from app.agents.experience.provider import ChatProvider, DeepSeekProvider
from app.contracts import DeviceState, Person, PlanGeneration, PlannerInfo, PlannerMode, PlanSource, RestPreference
from app.rules.rest_rule import adjustment_rule, rest_rule_text

# Harness rule: how far a model plan may move away from the person's authorised preference.
# Beyond this the plan is not trusted and the rule plan is used instead ("experience is the constraint").
MAX_DEVIATION = {"light_brightness": 40, "ac_target_temp_c": 3.0, "curtain_open_percent": 40}
_DEVIATION_LABEL = {"light_brightness": ("灯光", "%"), "ac_target_temp_c": ("空调", "°C"), "curtain_open_percent": ("窗帘", "%")}


def deviation_violation(pref: RestPreference, proposed: RestPreference) -> Optional[str]:
    """Return a readable reason if any setting deviates from the preference beyond MAX_DEVIATION."""
    for field, limit in MAX_DEVIATION.items():
        delta = getattr(proposed, field) - getattr(pref, field)
        if abs(delta) > limit:
            name, unit = _DEVIATION_LABEL[field]
            return f"模型建议偏离偏好过大（{name} {delta:+g}{unit}，上限 ±{limit:g}{unit}）"
    return None


@dataclass
class ExperienceOutcome:
    """The Experience Agent's output: a target, not device actions."""

    settings: RestPreference
    summary: str
    notes: list[str]
    source: PlanSource
    generation: PlanGeneration
    fallback_reason: Optional[str]


def _rule_generation(mode: PlannerMode, latency_ms: int, reason: Optional[str]) -> PlanGeneration:
    return PlanGeneration(
        mode_requested=mode, provider=None, model=None, latency_ms=latency_ms, fallback_reason=reason, goal=None
    )


def _adjustment_prompt(room_temp_c: float) -> str:
    return (
        f"【模拟环境事件】用户已经在休息，卧室室温现在是 {room_temp_c:g}°C。"
        "请给出调整后的设置：只调整确有必要的项，其余保持当前设备状态的数值；"
        "不要为了调整而打扰休息（例如不要调亮灯光、不要打开窗帘）。"
    )


class Planner:
    def __init__(
        self,
        default_mode: PlannerMode,
        provider: Optional[ChatProvider],
        timeout_s: float,
        clock: Callable,
    ):
        self.default_mode: PlannerMode = default_mode
        self._provider = provider
        self._timeout_s = timeout_s
        self._clock = clock
        self._agent = ExperienceAgent(provider, timeout_s) if provider else None

    def info(self) -> PlannerInfo:
        return PlannerInfo(
            default_mode=self.default_mode,
            model_configured=self._provider is not None,
            provider=self._provider.name if self._provider else None,
            model=self._provider.model if self._provider else None,
            timeout_ms=int(self._timeout_s * 1000),
        )

    def _model(self, person: Person, state: DeviceState, prompt: str):
        """Returns (settings, result, error_reason, latency_ms)."""
        started = time.monotonic()
        if self._agent is None:
            return None, None, "模型未配置（缺少 API key 或 provider）", 0
        try:
            result = self._agent.plan(person, state, prompt)
        except ExperienceError as exc:
            return None, None, exc.message, exc.latency_ms
        out = result.output
        settings = RestPreference(
            light_brightness=out.light_brightness,
            ac_target_temp_c=out.ac_target_temp_c,
            curtain_open_percent=out.curtain_open_percent,
        )
        elapsed = int((time.monotonic() - started) * 1000)
        assert person.rest_preference is not None
        too_far = deviation_violation(person.rest_preference, settings)
        if too_far:
            return None, None, too_far, elapsed
        return settings, result, None, elapsed

    def plan(self, person: Person, utterance: str, device_state: DeviceState, mode: Optional[PlannerMode]) -> ExperienceOutcome:
        """`person.rest_preference` must be the current preference (from memory)."""
        assert person.rest_preference is not None
        effective: PlannerMode = mode or self.default_mode
        if effective == "rule":
            summary, notes = rest_rule_text(person, None)
            return ExperienceOutcome(person.rest_preference, summary, notes, "rule", _rule_generation("rule", 0, None), None)

        settings, result, reason, latency = self._model(person, device_state, utterance)
        if settings is None:
            summary, notes = rest_rule_text(person, reason)
            return ExperienceOutcome(
                person.rest_preference, summary, notes, "rule_fallback", _rule_generation("model", latency, reason), reason
            )
        out = result.output
        notes = [f"模型计划：{result.provider} / {result.model}，{result.latency_ms} ms", f"理由：{out.rationale}"]
        if out.needs_clarification and out.clarification_question:
            notes.append(f"待确认：{out.clarification_question}")
        generation = PlanGeneration(
            mode_requested="model", provider=result.provider, model=result.model, latency_ms=latency, fallback_reason=None, goal=out.goal
        )
        return ExperienceOutcome(settings, out.goal, notes, "model", generation, None)

    def plan_adjustment(
        self, person: Person, room_temp_c: float, device_state: DeviceState, mode: PlannerMode
    ) -> ExperienceOutcome:
        """One adjustment after an environment event. Same fallback and deviation rules as plan()."""
        assert person.rest_preference is not None

        def rule(reason: Optional[str], latency_ms: int = 0) -> ExperienceOutcome:
            settings, summary = adjustment_rule(person.rest_preference, device_state, room_temp_c)
            note = (
                "规则调整：室温偏离设定 2°C 以上时，空调每次调整 1°C，且不超出偏好 ±3°C"
                if reason is None
                else f"规则降级：请求了模型，但改用调整规则（{reason}）"
            )
            source: PlanSource = "rule" if reason is None else "rule_fallback"
            return ExperienceOutcome(
                settings, summary, [note], source, _rule_generation("rule" if reason is None else "model", latency_ms, reason), reason
            )

        if mode == "rule":
            return rule(None)
        settings, result, reason, latency = self._model(person, device_state, _adjustment_prompt(room_temp_c))
        if settings is None:
            return rule(reason, latency)
        out = result.output
        generation = PlanGeneration(
            mode_requested="model", provider=result.provider, model=result.model, latency_ms=latency, fallback_reason=None, goal=out.goal
        )
        notes = [f"模型调整：{result.provider} / {result.model}，{result.latency_ms} ms", f"理由：{out.rationale}"]
        return ExperienceOutcome(settings, out.goal, notes, "model", generation, None)


def provider_from_config() -> Optional[ChatProvider]:
    if config.MODEL_PROVIDER == "deepseek" and config.DEEPSEEK_API_KEY:
        return DeepSeekProvider(config.DEEPSEEK_API_KEY, config.DEEPSEEK_MODEL, config.DEEPSEEK_BASE_URL)
    return None


def planner_from_config(clock: Callable) -> Planner:
    mode: PlannerMode = "model" if config.PLANNER_DEFAULT_MODE == "model" else "rule"
    return Planner(mode, provider_from_config(), config.MODEL_TIMEOUT_S, clock)

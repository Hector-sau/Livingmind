"""Planner: picks rule or model path and guarantees a plan comes back.

Model failures of any kind (not configured, timeout, network, HTTP, bad JSON, schema) produce a
rule fallback plan whose source is "rule_fallback" with the reason attached. Nothing here touches
devices.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Optional

from app import config
from app.agents.experience import ExperienceAgent, ExperienceError
from app.agents.experience.provider import ChatProvider, DeepSeekProvider
from app.contracts import DeviceState, Person, Plan, PlanGeneration, PlannerInfo, PlannerMode, RestPreference
from app.rules.rest_rule import build_plan, build_rest_plan


@dataclass
class PlanOutcome:
    plan: Plan
    fallback_reason: Optional[str]  # set when model mode degraded to rules


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

    def plan(
        self,
        person: Person,
        space_id: str,
        utterance: str,
        device_state: DeviceState,
        new_id: Callable[[str], str],
        mode: Optional[PlannerMode],
    ) -> PlanOutcome:
        effective: PlannerMode = mode or self.default_mode
        if effective == "rule":
            return PlanOutcome(build_rest_plan(person, space_id, utterance, self._clock(), new_id), None)

        started = time.monotonic()
        if self._agent is None:
            reason = "模型未配置（缺少 API key 或 provider）"
            return PlanOutcome(
                build_rest_plan(person, space_id, utterance, self._clock(), new_id, latency_ms=0, fallback_reason=reason),
                reason,
            )
        try:
            result = self._agent.plan(person, device_state, utterance)
        except ExperienceError as exc:
            return PlanOutcome(
                build_rest_plan(
                    person, space_id, utterance, self._clock(), new_id, latency_ms=exc.latency_ms, fallback_reason=exc.message
                ),
                exc.message,
            )

        out = result.output
        settings = RestPreference(
            light_brightness=out.light_brightness,
            ac_target_temp_c=out.ac_target_temp_c,
            curtain_open_percent=out.curtain_open_percent,
        )
        notes = [f"模型计划：{result.provider} / {result.model}，{result.latency_ms} ms", f"理由：{out.rationale}"]
        if out.needs_clarification and out.clarification_question:
            notes.append(f"待确认：{out.clarification_question}")
        plan = build_plan(
            person=person,
            space_id=space_id,
            utterance=utterance,
            now=self._clock(),
            new_id=new_id,
            settings=settings,
            source="model",
            summary=out.goal,
            notes=notes,
            generation=PlanGeneration(
                mode_requested="model",
                provider=result.provider,
                model=result.model,
                latency_ms=int((time.monotonic() - started) * 1000),
                fallback_reason=None,
                goal=out.goal,
            ),
        )
        return PlanOutcome(plan, None)


def provider_from_config() -> Optional[ChatProvider]:
    if config.MODEL_PROVIDER == "deepseek" and config.DEEPSEEK_API_KEY:
        return DeepSeekProvider(config.DEEPSEEK_API_KEY, config.DEEPSEEK_MODEL, config.DEEPSEEK_BASE_URL)
    return None


def planner_from_config(clock: Callable) -> Planner:
    mode: PlannerMode = "model" if config.PLANNER_DEFAULT_MODE == "model" else "rule"
    return Planner(mode, provider_from_config(), config.MODEL_TIMEOUT_S, clock)

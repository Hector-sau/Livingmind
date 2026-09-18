"""Comparing a legacy plan with a graph plan.

Ids, timestamps and latencies always differ, so equality is defined on what the user and the
devices actually see. Used by the double-path test and by scripts/compare_orchestrators.py.
"""

from __future__ import annotations

from typing import Any

from app.contracts import Plan


def plan_fingerprint(plan: Plan) -> dict[str, Any]:
    return {
        "scenario": plan.scenario,
        "source": plan.source,
        "summary": plan.summary,
        "notes": list(plan.notes),
        "utterance": plan.utterance,
        "wake_time": plan.wake_time,
        "fallback_reason": plan.generation.fallback_reason,
        "mode_requested": plan.generation.mode_requested,
        "actions": [(a.device, a.command, a.value, a.label) for a in plan.actions],
        "schedule": [
            (s.at, s.phase, s.title, [(a.device, a.command, a.value) for a in s.actions]) for s in plan.schedule
        ],
        "energy": None
        if plan.energy is None
        else (
            plan.energy.mode,
            plan.energy.tariff,
            plan.energy.recommended_ac_c,
            plan.energy.applied,
            plan.energy.comfort_min_c,
            plan.energy.comfort_max_c,
        ),
        "trace_agents": [(step.agent, step.ok) for step in plan.trace],
    }


def plan_equivalent(left: Plan, right: Plan) -> bool:
    return plan_fingerprint(left) == plan_fingerprint(right)


def fingerprint_diff(left: Plan, right: Plan) -> dict[str, tuple[Any, Any]]:
    a, b = plan_fingerprint(left), plan_fingerprint(right)
    return {k: (a[k], b[k]) for k in a if a[k] != b[k]}

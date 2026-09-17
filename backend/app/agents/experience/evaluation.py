"""Scoring for the Experience Agent evaluation set (backend/evals/experience_cases.json).

Each case states, per setting, the expected direction relative to the person's preference:
lower / same / higher / any, or "guarded" (the request would exceed the deviation limit, so the
final plan must stay within the limit — either the model held back or the harness fell back).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from app.contracts import Plan, RestPreference
from app.services.planner import MAX_DEVIATION

CASES_PATH = Path(__file__).resolve().parents[3] / "evals" / "experience_cases.json"
FIELDS = {"light": "light_brightness", "ac": "ac_target_temp_c", "curtain": "curtain_open_percent"}
TOLERANCE = {"light_brightness": 5, "ac_target_temp_c": 0.5, "curtain_open_percent": 5}
DEVICE = {"light": "light", "ac": "ac", "curtain": "curtain"}
Expectation = Literal["lower", "same", "higher", "any", "guarded"]
Verdict = Literal["pass", "fail", "fallback"]


@dataclass
class CaseScore:
    case_id: str
    verdict: Verdict
    details: list[str] = field(default_factory=list)


def load_cases(path: Path = CASES_PATH) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))["cases"]


def plan_settings(plan: Plan) -> dict[str, float]:
    values = {a.device: float(a.value) for a in plan.actions}
    return {"light": values["light"], "ac": values["ac"], "curtain": values["curtain"]}


def direction(delta: float, tol: float) -> str:
    if abs(delta) <= tol:
        return "same"
    return "higher" if delta > 0 else "lower"


def score_case(case: dict, pref: RestPreference, plan: Plan) -> CaseScore:
    settings = plan_settings(plan)
    guarded = any(v == "guarded" for v in case["expect"].values())
    if plan.source == "rule_fallback" and not guarded:
        return CaseScore(case["id"], "fallback", [plan.generation.fallback_reason or "fallback"])
    details, ok = [], True
    for short, expect in case["expect"].items():
        attr = FIELDS[short]
        delta = settings[short] - float(getattr(pref, attr))
        if expect == "any":
            continue
        if expect == "guarded":
            within = abs(delta) <= MAX_DEVIATION[attr]
            details.append(f"{short}: Δ{delta:+g} {'在上限内' if within else '超出上限'}")
            ok &= within
            continue
        got = direction(delta, TOLERANCE[attr])
        if got != expect:
            ok = False
            details.append(f"{short}: 期望 {expect}，实际 {got}（Δ{delta:+g}）")
    return CaseScore(case["id"], "pass" if ok else "fail", details)

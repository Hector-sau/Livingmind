"""Deterministic Harness policy used at planning, confirmation and execution time."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from app.contracts import DeviceAction, Plan, PolicyDecision, PolicyRuleResult

# Platform safety policy. Real-device capability ranges are intersected with this policy
# when an ExecutionGrant is created; neither the model nor the client can widen it.
ALLOWED_COMMANDS: dict[tuple[str, str], tuple[float, float, bool]] = {
    ("light", "set_brightness"): (0, 100, True),
    ("ac", "set_target_temperature"): (16, 30, False),
    ("curtain", "set_open_percent"): (0, 100, True),
}

POLICY_VERSION = "livingmind-device-policy-v1"


def validate_action(action: DeviceAction) -> Optional[str]:
    rule = ALLOWED_COMMANDS.get((action.device, action.command))
    if rule is None:
        return f"工具不在白名单：{action.device}.{action.command}"
    low, high, integer_only = rule
    if not (low <= action.value <= high):
        return f"参数超出范围：{action.value:g}（允许 {low:g}–{high:g}）"
    if integer_only and float(action.value) != int(action.value):
        return f"参数必须是整数：{action.value:g}"
    return None


def precheck(actions: list[DeviceAction]) -> tuple[list[DeviceAction], list[str]]:
    """Split actions into allowed ones and readable violations."""
    allowed, problems = [], []
    for a in actions:
        reason = validate_action(a)
        if reason:
            problems.append(f"{a.label}：{reason}")
        else:
            allowed.append(a)
    return allowed, problems


def evaluate_plan(plan: Plan, *, decision_id: str, plan_hash: str, decided_at: datetime) -> PolicyDecision:
    """Create an auditable decision without producing device side effects."""

    actions = [*plan.actions, *(action for step in plan.schedule for action in step.actions)]
    checks: list[PolicyRuleResult] = []
    reasons: list[str] = []
    for action in actions:
        problem = validate_action(action)
        checks.append(
            PolicyRuleResult(
                rule=f"allowlist:{action.device}.{action.command}",
                passed=problem is None,
                detail=problem or f"{action.value:g} 在平台安全范围内",
            )
        )
        if problem:
            reasons.append(f"{action.label}：{problem}")

    # Empty plans are valid answers but carry no device authority.
    decision = "deny" if reasons else "require_confirmation"
    if not actions:
        decision = "allow"
    return PolicyDecision(
        decision_id=decision_id,
        plan_id=plan.plan_id,
        plan_version=plan.version,
        space_id=plan.space_id,
        policy_version=POLICY_VERSION,
        decision=decision,
        plan_hash=plan_hash,
        checks=checks,
        reasons=reasons,
        decided_at=decided_at,
    )

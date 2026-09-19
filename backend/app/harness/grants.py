"""Immutable plan hashing and bounded execution grants.

Confirmation creates authority for a particular person, space, plan version and space
epoch. The grant can narrow device capabilities but can never widen the platform policy.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from typing import Optional

from app.contracts import Capability, DeviceAction, ExecutionGrant, Plan, PolicyDecision, RequestContext
from app.harness.policy import ALLOWED_COMMANDS


def _bounded_capabilities(plan: Plan, capabilities: list[Capability], *, service_id: Optional[str]) -> list[Capability]:
    """Intersect device capabilities with platform policy and the approved plan surface.

    A direct command receives authority for exactly its approved value. A long-running
    service may issue later schedule/event actions, so it receives the safe range only
    for device/command pairs that appeared in the confirmed plan or schedule.
    """

    approved_actions = [*plan.actions, *(action for step in plan.schedule for action in step.actions)]
    approved: dict[tuple[str, str], list[float]] = {}
    for action in approved_actions:
        approved.setdefault((action.device, action.command), []).append(float(action.value))

    bounded: list[Capability] = []
    for capability in capabilities:
        key = (capability.device, capability.command)
        values = approved.get(key)
        platform = ALLOWED_COMMANDS.get(key)
        if not values or platform is None:
            continue
        platform_min, platform_max, platform_integer = platform
        low = max(float(capability.min), platform_min)
        high = min(float(capability.max), platform_max)
        if service_id is None:
            # The confirmation authorizes only what the direct command displayed.
            low = max(low, min(values))
            high = min(high, max(values))
        if low <= high:
            bounded.append(
                Capability(
                    device=capability.device,
                    command=capability.command,
                    min=low,
                    max=high,
                    integer=capability.integer or platform_integer,
                )
            )
    return bounded


def semantic_plan_hash(plan: Plan) -> str:
    payload = {
        "plan_id": plan.plan_id,
        "version": plan.version,
        "person_id": plan.person_id,
        "space_id": plan.space_id,
        "scenario": plan.scenario,
        "actions": [action.model_dump(mode="json") for action in plan.actions],
        "schedule": [step.model_dump(mode="json") for step in plan.schedule],
        "expires_at": plan.expires_at.isoformat(),
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def create_execution_grant(
    *,
    grant_id: str,
    decision: PolicyDecision,
    plan: Plan,
    context: RequestContext,
    service_id: Optional[str],
    service_epoch: int,
    capabilities: list[Capability],
    max_adjustments: int,
    now: datetime,
) -> ExecutionGrant:
    # Direct commands only need a short grant. A confirmed rest service may span the
    # simulated night, so it receives a bounded 12-hour service authority.
    valid_until = plan.expires_at if service_id is None else max(plan.expires_at, now + timedelta(hours=12))
    return ExecutionGrant(
        grant_id=grant_id,
        policy_decision_id=decision.decision_id,
        account_id=context.account_id,
        person_id=context.person_id,
        space_id=context.space_id,
        plan_id=plan.plan_id,
        plan_version=plan.version,
        plan_hash=decision.plan_hash,
        service_id=service_id,
        service_epoch=service_epoch,
        capabilities=_bounded_capabilities(plan, capabilities, service_id=service_id),
        max_adjustments=max_adjustments,
        status="active",
        created_at=now,
        valid_until=valid_until,
        revoked_at=None,
    )


def grant_denial_reason(
    grant: ExecutionGrant,
    action: DeviceAction,
    *,
    now: datetime,
    service_epoch: int,
    service_id: Optional[str],
) -> Optional[str]:
    if grant.status != "active":
        return "执行授权已撤销或过期"
    if now > grant.valid_until:
        return "执行授权已过期"
    if grant.service_epoch != service_epoch:
        return "执行授权的空间代次已失效"
    if grant.service_id != service_id:
        return "执行授权不属于当前服务"
    capability = next(
        (item for item in grant.capabilities if item.device == action.device and item.command == action.command),
        None,
    )
    if capability is None:
        return f"执行授权不允许：{action.device}.{action.command}"
    if not (capability.min <= action.value <= capability.max):
        return f"动作超出授权范围：{action.value:g}"
    if capability.integer and float(action.value) != int(action.value):
        return f"授权要求整数参数：{action.value:g}"
    return None

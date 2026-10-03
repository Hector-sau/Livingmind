"""Where the demo's business facts live.

Two implementations behind one protocol:
- ``MemoryStore``: process memory, resets on restart (the demo default).
- ``SqlStore``: PostgreSQL, survives restarts (T2).

Both return **copies**. Callers must therefore save explicitly after every mutation, so a
missing save fails the same way in memory as it does on PostgreSQL — there is no code path
that silently works only because two variables happened to be the same object.

Concurrency: a single API process still serialises bookkeeping with the service lock; the
database adds the durable constraints (one active service per space, step claimed once).
Multi-instance coordination is T4, not this step.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import Optional, Protocol

from app.contracts import (
    ActionExecution,
    ActionResult,
    ActivityRecord,
    ExecutionGrant,
    PendingClarification,
    Plan,
    PolicyDecision,
    ScheduledStep,
    Service,
)
from app.events.envelope import Envelope

# Flags for work in flight on one service. They are process/transaction level, not user data.
FLAG_REPLANNING = "replanning"  # an environment adjustment is being planned or executed
FLAG_ADVANCING = "advancing"  # the night clock is running one or more steps


@dataclass
class PlanRecord:
    plan: Plan
    epoch: int  # space epoch at creation; a stop bumps the epoch and invalidates older plans
    results: list[ActionResult] = field(default_factory=list)
    service_id: Optional[str] = None


class Store(Protocol):
    def new_id(self, prefix: str) -> str: ...

    # ---- space epoch: a stop or a reset invalidates everything planned before it ----
    def epoch(self, space_id: str) -> int: ...

    def bump_epoch(self, space_id: str) -> int: ...

    # ---- plans ----
    def save_plan(self, record: PlanRecord, events: Optional[list[Envelope]] = None) -> None:
        """Save the plan and, in the same transaction, any domain events it produced."""
        ...

    def get_plan(self, plan_id: str) -> Optional[PlanRecord]: ...

    def append_result(self, plan_id: str, result: ActionResult) -> None: ...

    def invalidate_proposed_plans(self, space_id: str) -> None: ...

    # ---- services and their overnight steps ----
    def save_service(self, service: Service, events: Optional[list[Envelope]] = None) -> None: ...

    def get_service(self, service_id: str) -> Optional[Service]: ...

    def active_service(self, space_id: str) -> Optional[Service]: ...

    def claim_steps(self, service_id: str, step_ids: list[str]) -> list[str]:
        """Move the given steps from pending to running. Returns the ids actually claimed."""
        ...

    def save_step(self, service_id: str, step: ScheduledStep) -> None: ...

    # ---- work-in-flight flags ----
    def acquire_flag(self, service_id: str, flag: str) -> bool: ...

    def release_flag(self, service_id: str, flag: str) -> None: ...

    def has_flag(self, service_id: str, flag: str) -> bool: ...

    # ---- resumable clarification ----
    def save_clarification(self, clarification: PendingClarification) -> None: ...

    def get_clarification(self, conversation_id: str) -> Optional[PendingClarification]: ...

    def delete_clarification(self, conversation_id: str) -> None: ...

    # ---- execution authority and durable command ledger ----
    def save_policy_decision(self, decision: PolicyDecision) -> None: ...

    def get_policy_decision(self, decision_id: str) -> Optional[PolicyDecision]: ...

    def save_grant(self, grant: ExecutionGrant) -> None: ...

    def get_grant(self, grant_id: str) -> Optional[ExecutionGrant]: ...

    def grant_for_service(self, service_id: str) -> Optional[ExecutionGrant]: ...

    def revoke_grants(self, space_id: str, revoked_at) -> int: ...

    def save_action_execution(self, execution: ActionExecution) -> None: ...

    def get_action_execution(self, action_id: str) -> Optional[ActionExecution]: ...

    def resolve_unknown_action(self, execution: ActionExecution, result: ActionResult) -> Optional[ActionExecution]: ...

    def unresolved_action_executions(self) -> list[ActionExecution]: ...

    def recent_action_executions(self, space_id: str) -> list[ActionExecution]: ...

    # ---- activity ----
    def append_activity(self, record: ActivityRecord) -> None: ...

    def activity(self, space_id: str, limit: int) -> list[ActivityRecord]: ...

    def record_events(self, events: list[Envelope]) -> None:
        """Only for facts that are not a plan or service save (preference, energy mode)."""
        ...

    def clear(self) -> None: ...

    def startup_reconcile(self) -> dict[str, int]: ...


def _copy_service(service: Service) -> Service:
    return service.model_copy(deep=True)


class MemoryStore:
    """Process memory. Kept as the default so the demo runs with no infrastructure."""

    def __init__(self) -> None:
        self._plans: dict[str, PlanRecord] = {}
        self._services: dict[str, Service] = {}
        self._activity: list[ActivityRecord] = []
        self._epochs: dict[str, int] = {}
        self._flags: set[tuple[str, str]] = set()
        self._clarifications: dict[str, PendingClarification] = {}
        self._policy_decisions: dict[str, PolicyDecision] = {}
        self._grants: dict[str, ExecutionGrant] = {}
        self._action_executions: dict[str, ActionExecution] = {}
        self._events: list[Envelope] = []
        self._counter = itertools.count(1)

    def new_id(self, prefix: str) -> str:
        return f"{prefix}-{next(self._counter):05d}"

    def epoch(self, space_id: str) -> int:
        return self._epochs.get(space_id, 0)

    def bump_epoch(self, space_id: str) -> int:
        self._epochs[space_id] = self.epoch(space_id) + 1
        return self._epochs[space_id]

    def save_plan(self, record: PlanRecord, events: Optional[list[Envelope]] = None) -> None:
        self.record_events(events or [])
        self._plans[record.plan.plan_id] = PlanRecord(
            plan=record.plan.model_copy(deep=True),
            epoch=record.epoch,
            results=[r.model_copy() for r in record.results],
            service_id=record.service_id,
        )

    def get_plan(self, plan_id: str) -> Optional[PlanRecord]:
        stored = self._plans.get(plan_id)
        if stored is None:
            return None
        return PlanRecord(
            plan=stored.plan.model_copy(deep=True),
            epoch=stored.epoch,
            results=[r.model_copy() for r in stored.results],
            service_id=stored.service_id,
        )

    def append_result(self, plan_id: str, result: ActionResult) -> None:
        stored = self._plans.get(plan_id)
        if stored is not None and not any(item.action_id == result.action_id for item in stored.results):
            stored.results.append(result.model_copy())

    def invalidate_proposed_plans(self, space_id: str) -> None:
        for stored in self._plans.values():
            if stored.plan.space_id == space_id and stored.plan.status == "proposed":
                stored.plan.status = "invalidated"

    def save_service(self, service: Service, events: Optional[list[Envelope]] = None) -> None:
        self.record_events(events or [])
        self._services[service.service_id] = _copy_service(service)

    def get_service(self, service_id: str) -> Optional[Service]:
        stored = self._services.get(service_id)
        return _copy_service(stored) if stored else None

    def active_service(self, space_id: str) -> Optional[Service]:
        for service in self._services.values():
            if service.space_id == space_id and service.status == "active":
                return _copy_service(service)
        return None

    def claim_steps(self, service_id: str, step_ids: list[str]) -> list[str]:
        stored = self._services.get(service_id)
        if stored is None:
            return []
        claimed = []
        for step in stored.schedule:
            if step.step_id in step_ids and step.status == "pending":
                step.status = "running"
                claimed.append(step.step_id)
        return claimed

    def save_step(self, service_id: str, step: ScheduledStep) -> None:
        stored = self._services.get(service_id)
        if stored is None:
            return
        for index, existing in enumerate(stored.schedule):
            if existing.step_id == step.step_id:
                stored.schedule[index] = step.model_copy(deep=True)
                return

    def acquire_flag(self, service_id: str, flag: str) -> bool:
        key = (service_id, flag)
        if key in self._flags:
            return False
        self._flags.add(key)
        return True

    def release_flag(self, service_id: str, flag: str) -> None:
        self._flags.discard((service_id, flag))

    def has_flag(self, service_id: str, flag: str) -> bool:
        return (service_id, flag) in self._flags

    def save_clarification(self, clarification: PendingClarification) -> None:
        self._clarifications[clarification.conversation_id] = clarification.model_copy(deep=True)

    def get_clarification(self, conversation_id: str) -> Optional[PendingClarification]:
        item = self._clarifications.get(conversation_id)
        return item.model_copy(deep=True) if item else None

    def delete_clarification(self, conversation_id: str) -> None:
        self._clarifications.pop(conversation_id, None)

    def save_policy_decision(self, decision: PolicyDecision) -> None:
        self._policy_decisions[decision.decision_id] = decision.model_copy(deep=True)

    def get_policy_decision(self, decision_id: str) -> Optional[PolicyDecision]:
        item = self._policy_decisions.get(decision_id)
        return item.model_copy(deep=True) if item else None

    def save_grant(self, grant: ExecutionGrant) -> None:
        self._grants[grant.grant_id] = grant.model_copy(deep=True)

    def get_grant(self, grant_id: str) -> Optional[ExecutionGrant]:
        item = self._grants.get(grant_id)
        return item.model_copy(deep=True) if item else None

    def grant_for_service(self, service_id: str) -> Optional[ExecutionGrant]:
        matches = [grant for grant in self._grants.values() if grant.service_id == service_id]
        if not matches:
            return None
        return max(matches, key=lambda grant: grant.created_at).model_copy(deep=True)

    def revoke_grants(self, space_id: str, revoked_at) -> int:
        count = 0
        for grant in self._grants.values():
            if grant.space_id == space_id and grant.status == "active":
                grant.status = "revoked"
                grant.revoked_at = revoked_at
                count += 1
        return count

    def save_action_execution(self, execution: ActionExecution) -> None:
        current = self._action_executions.get(execution.action_id)
        if current and current.status in ("completed", "failed", "rejected", "cancelled"):
            return  # a late timeout callback cannot erase a reconciled terminal result
        self._action_executions[execution.action_id] = execution.model_copy(deep=True)

    def get_action_execution(self, action_id: str) -> Optional[ActionExecution]:
        item = self._action_executions.get(action_id)
        return item.model_copy(deep=True) if item else None

    def resolve_unknown_action(self, execution: ActionExecution, result: ActionResult) -> Optional[ActionExecution]:
        current = self.get_action_execution(execution.action_id)
        if current is None or current.status != "unknown":
            return current
        execution = execution.model_copy(update={"last_checked_at": execution.completed_at,
                                                  "next_check_at": None, "recovery_exhausted": False})
        self.save_action_execution(execution)
        record = self._plans.get(execution.plan_id)
        from app.harness.reconciliation import reconciliation_activity
        if record:
            present = any(item.action_id == execution.action_id for item in record.results)
            record.results = [result.model_copy(deep=True) if item.action_id == execution.action_id
                              and item.outcome == "unknown" else item for item in record.results]
            if not present:
                record.results.append(result.model_copy(deep=True))
        self.append_activity(reconciliation_activity(execution, result,
                             execution.person_id or (record.plan.person_id if record else None)))
        return execution.model_copy(deep=True)

    def recent_action_executions(self, space_id: str) -> list[ActionExecution]:
        return [item.model_copy(deep=True) for item in reversed(list(self._action_executions.values()))
                if item.space_id == space_id][:200]

    def unresolved_action_executions(self) -> list[ActionExecution]:
        return [
            item.model_copy(deep=True)
            for item in self._action_executions.values()
            if item.status in ("dispatching", "accepted", "unknown")
        ]

    def append_activity(self, record: ActivityRecord) -> None:
        self._activity.append(record.model_copy(deep=True))

    def activity(self, space_id: str, limit: int) -> list[ActivityRecord]:
        items = [a for a in self._activity if a.space_id == space_id]
        return [a.model_copy(deep=True) for a in reversed(items)][:limit]

    def record_events(self, events: list[Envelope]) -> None:
        # No bus in memory mode: events are kept so tests can assert what would be published.
        self._events.extend(events)

    def pending_events(self) -> list[Envelope]:
        return list(self._events)

    def clear(self) -> None:
        # Reset invalidates work that may still be outside the service lock in a
        # slow device adapter. Never clear epochs back to zero: an old request
        # must not become valid again after the demo state is recreated.
        space_ids = set(self._epochs)
        space_ids.update(record.plan.space_id for record in self._plans.values())
        space_ids.update(service.space_id for service in self._services.values())
        next_epochs = {space_id: self.epoch(space_id) + 1 for space_id in space_ids}
        self._plans.clear()
        self._services.clear()
        self._activity.clear()
        self._epochs = next_epochs
        self._flags.clear()
        self._clarifications.clear()
        self._policy_decisions.clear()
        self._grants.clear()
        self._action_executions.clear()
        self._events.clear()

    def startup_reconcile(self) -> dict[str, int]:
        return {
            "active_services": 0,
            "cancelled_unknown_steps": 0,
            "cleared_inflight_flags": 0,
            "unknown_actions": 0,
        }

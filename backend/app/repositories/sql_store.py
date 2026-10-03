"""PostgreSQL implementation of the business-fact store (T2).

Shape: real columns for everything the database must query or enforce (ids, space, status,
epoch, step order), plus a JSONB payload holding the exact contract model. The payload keeps
API responses identical to the in-memory demo; the columns carry the constraints:

- one active service per space  -> partial unique index
- a night step runs at most once -> UPDATE ... WHERE status='pending' RETURNING
- work in flight                 -> service_flags rows, inserted inside the caller's lock
- ids                            -> a database sequence, so restarts never reuse an id
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import cast, func, select, text, update
from sqlalchemy.dialects.postgresql import JSONB

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
from app.db.models import (
    ActionExecutionRow,
    ActivityRow,
    ExecutionGrantRow,
    OutboxEventRow,
    PendingClarificationRow,
    PlanRow,
    PolicyDecisionRow,
    ScheduledStepRow,
    ServiceFlagRow,
    ServiceRow,
    SpaceStateRow,
    SharedSettingRow,
)
from app.events.envelope import Envelope
from app.db.session import session_scope
from app.repositories.store import PlanRecord
from app.repositories.action_recovery import ActionRecoveryStore


def _service_from_row(row: ServiceRow, steps: list[ScheduledStepRow]) -> Service:
    payload = dict(row.payload)
    payload["schedule"] = [step.payload for step in sorted(steps, key=lambda s: s.ordinal)]
    return Service.model_validate(payload)


class SqlStore(ActionRecoveryStore):
    owner_id = None  # set by remote-gateway RestService after acquiring its owner lock

    def get_setting(self, key):
        with session_scope() as session:
            row = session.get(SharedSettingRow, key)
            return dict(row.payload) if row else None

    def set_setting(self, key, value):
        from sqlalchemy.dialects.postgresql import insert
        with session_scope() as session:
            if value is None:
                session.query(SharedSettingRow).filter_by(key=key).delete()
            else:
                session.execute(insert(SharedSettingRow).values(key=key, payload=value).on_conflict_do_update(
                    index_elements=[SharedSettingRow.key], set_={"payload": value}))

    # ---- ids ----

    def new_id(self, prefix: str) -> str:
        with session_scope() as session:
            value = session.scalar(text("select nextval('livingmind_id_seq')"))
        return f"{prefix}-{int(value):05d}"

    # ---- space epoch ----

    def epoch(self, space_id: str) -> int:
        with session_scope() as session:
            row = session.get(SpaceStateRow, space_id)
            return row.epoch if row else 0

    def bump_epoch(self, space_id: str) -> int:
        with session_scope() as session:
            row = session.get(SpaceStateRow, space_id, with_for_update=True)
            if row is None:
                row = SpaceStateRow(space_id=space_id, epoch=1)
                session.add(row)
                return 1
            row.epoch += 1
            return row.epoch

    # ---- plans ----

    @staticmethod
    def _write_events(session, events) -> None:
        """Outbox rows are written inside the caller's transaction: business fact and event
        commit together, or neither does. Serialize same-space inserts until commit so
        outbox sequence allocation cannot overtake an uncommitted earlier event."""
        from sqlalchemy import text

        events = list(events or [])
        # Ordered acquisition also avoids deadlocks if one transaction spans spaces.
        for space_id in sorted({envelope.space_id for envelope in events}):
            session.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:space_id, 0))"),
                {"space_id": f"livingmind-outbox:{space_id}"},
            )
        for envelope in events:
            session.add(
                OutboxEventRow(
                    event_id=envelope.event_id,
                    event_type=envelope.event_type,
                    space_id=envelope.space_id,
                    payload=envelope.model_dump(mode="json", by_alias=True),
                )
            )

    def record_events(self, events: list[Envelope]) -> None:
        with session_scope() as session:
            self._write_events(session, events)

    def save_plan(self, record: PlanRecord, events: Optional[list[Envelope]] = None) -> None:
        plan = record.plan
        with session_scope() as session:
            self._write_events(session, events)
            row = session.get(PlanRow, plan.plan_id)
            if row is None:
                row = PlanRow(plan_id=plan.plan_id)
                session.add(row)
            row.space_id = plan.space_id
            row.person_id = plan.person_id
            row.status = plan.status
            row.epoch = record.epoch
            row.service_id = record.service_id
            row.payload = plan.model_dump(mode="json")
            row.results = [r.model_dump(mode="json") for r in record.results]

    def get_plan(self, plan_id: str) -> Optional[PlanRecord]:
        with session_scope() as session:
            row = session.get(PlanRow, plan_id)
            if row is None:
                return None
            return PlanRecord(
                plan=Plan.model_validate(row.payload),
                epoch=row.epoch,
                results=[ActionResult.model_validate(r) for r in row.results],
                service_id=row.service_id,
            )

    def append_result(self, plan_id: str, result: ActionResult) -> None:
        with session_scope() as session:
            row = session.get(PlanRow, plan_id, with_for_update=True)
            if row is None:
                return
            # Reconciliation may have filled this result while the original
            # request was still returning an unknown outcome. Never append it twice.
            if any(item.get("action_id") == result.action_id for item in row.results):
                return
            row.results = [*row.results, result.model_dump(mode="json")]

    def invalidate_proposed_plans(self, space_id: str) -> None:
        with session_scope() as session:
            rows = session.scalars(
                select(PlanRow).where(PlanRow.space_id == space_id, PlanRow.status == "proposed").with_for_update()
            ).all()
            for row in rows:
                row.status = "invalidated"
                row.payload = {**row.payload, "status": "invalidated"}

    # ---- services ----

    def save_service(self, service: Service, events: Optional[list[Envelope]] = None) -> None:
        with session_scope() as session:
            row = session.get(ServiceRow, service.service_id, with_for_update=True)
            # A late adjustment snapshot must not resurrect a service stopped elsewhere.
            if row is not None and ((row.status == "stopped" and service.status != "stopped") or
                                    (row.status in ("completed", "failed") and service.status == "active")):
                return
            self._write_events(session, events)
            if row is None:
                row = ServiceRow(service_id=service.service_id)
                session.add(row)
            row.space_id = service.space_id
            row.person_id = service.person_id
            row.plan_id = service.plan_id
            row.status = service.status
            # Only an active service occupies the space (partial unique index).
            row.active_space_id = service.space_id if service.status == "active" else None
            payload = service.model_dump(mode="json")
            steps = payload.pop("schedule", [])
            row.payload = payload
            existing = {s.step_id: s for s in session.scalars(
                select(ScheduledStepRow).where(ScheduledStepRow.service_id == service.service_id)
            ).all()}
            for ordinal, step in enumerate(steps):
                step_row = existing.get(step["step_id"])
                if step_row is None:
                    step_row = ScheduledStepRow(step_id=step["step_id"], service_id=service.service_id)
                    session.add(step_row)
                step_row.ordinal = ordinal
                step_row.status = step["status"]
                step_row.payload = step

    def get_service(self, service_id: str) -> Optional[Service]:
        with session_scope() as session:
            row = session.get(ServiceRow, service_id)
            if row is None:
                return None
            steps = session.scalars(
                select(ScheduledStepRow).where(ScheduledStepRow.service_id == service_id)
            ).all()
            return _service_from_row(row, list(steps))

    def active_service(self, space_id: str) -> Optional[Service]:
        with session_scope() as session:
            row = session.scalar(
                select(ServiceRow).where(ServiceRow.space_id == space_id, ServiceRow.status == "active")
            )
            if row is None:
                return None
            steps = session.scalars(
                select(ScheduledStepRow).where(ScheduledStepRow.service_id == row.service_id)
            ).all()
            return _service_from_row(row, list(steps))

    def claim_steps(self, service_id: str, step_ids: list[str]) -> list[str]:
        """Atomic claim: only rows still pending change, and only this caller gets them."""
        if not step_ids:
            return []
        with session_scope() as session:
            claimed = session.scalars(
                update(ScheduledStepRow)
                .where(
                    ScheduledStepRow.service_id == service_id,
                    ScheduledStepRow.step_id.in_(step_ids),
                    ScheduledStepRow.status == "pending",
                )
                .values(
                    status="running",
                    owner_id=self.owner_id,
                    payload=ScheduledStepRow.payload.op("||")(cast(text("'{\"status\": \"running\"}'"), JSONB)),
                )
                .returning(ScheduledStepRow.step_id)
            ).all()
            return list(claimed)

    def save_step(self, service_id: str, step: ScheduledStep) -> None:
        with session_scope() as session:
            row = session.get(ScheduledStepRow, step.step_id)
            if row is None or row.service_id != service_id:
                return
            row.status = step.status
            row.payload = step.model_dump(mode="json")

    # ---- work-in-flight flags ----

    def acquire_flag(self, service_id: str, flag: str) -> bool:
        with session_scope() as session:
            if session.get(ServiceFlagRow, (service_id, flag)) is not None:
                return False
            session.add(ServiceFlagRow(service_id=service_id, flag=flag, owner_id=self.owner_id))
            return True

    def release_flag(self, service_id: str, flag: str) -> None:
        with session_scope() as session:
            row = session.get(ServiceFlagRow, (service_id, flag))
            if row is not None:
                session.delete(row)

    def has_flag(self, service_id: str, flag: str) -> bool:
        with session_scope() as session:
            return session.get(ServiceFlagRow, (service_id, flag)) is not None

    # ---- resumable clarification ----

    def save_clarification(self, clarification: PendingClarification) -> None:
        with session_scope() as session:
            row = session.get(PendingClarificationRow, clarification.conversation_id)
            values = {
                "account_id": clarification.account_id,
                "person_id": clarification.person_id,
                "space_id": clarification.space_id,
                "expires_at": clarification.expires_at,
                "payload": clarification.model_dump(mode="json"),
            }
            if row is None:
                session.add(PendingClarificationRow(conversation_id=clarification.conversation_id, **values))
            else:
                for key, value in values.items():
                    setattr(row, key, value)

    def get_clarification(self, conversation_id: str) -> Optional[PendingClarification]:
        with session_scope() as session:
            row = session.get(PendingClarificationRow, conversation_id)
            return PendingClarification.model_validate(row.payload) if row else None

    def delete_clarification(self, conversation_id: str) -> None:
        with session_scope() as session:
            row = session.get(PendingClarificationRow, conversation_id)
            if row is not None:
                session.delete(row)

    # ---- execution authority and durable command ledger ----

    def save_policy_decision(self, decision: PolicyDecision) -> None:
        with session_scope() as session:
            row = session.get(PolicyDecisionRow, decision.decision_id)
            if row is None:
                row = PolicyDecisionRow(decision_id=decision.decision_id)
                session.add(row)
            row.plan_id = decision.plan_id
            row.space_id = decision.space_id
            row.decision = decision.decision
            row.payload = decision.model_dump(mode="json")

    def get_policy_decision(self, decision_id: str) -> Optional[PolicyDecision]:
        with session_scope() as session:
            row = session.get(PolicyDecisionRow, decision_id)
            return PolicyDecision.model_validate(row.payload) if row else None

    def save_grant(self, grant: ExecutionGrant) -> None:
        with session_scope() as session:
            row = session.get(ExecutionGrantRow, grant.grant_id)
            if row is None:
                row = ExecutionGrantRow(grant_id=grant.grant_id)
                session.add(row)
            row.plan_id = grant.plan_id
            row.service_id = grant.service_id
            row.space_id = grant.space_id
            row.status = grant.status
            row.service_epoch = grant.service_epoch
            row.valid_until = grant.valid_until
            row.payload = grant.model_dump(mode="json")

    def get_grant(self, grant_id: str) -> Optional[ExecutionGrant]:
        with session_scope() as session:
            row = session.get(ExecutionGrantRow, grant_id)
            return ExecutionGrant.model_validate(row.payload) if row else None

    def grant_for_service(self, service_id: str) -> Optional[ExecutionGrant]:
        with session_scope() as session:
            row = session.scalar(
                select(ExecutionGrantRow)
                .where(ExecutionGrantRow.service_id == service_id)
                .order_by(ExecutionGrantRow.created_at.desc())
                .limit(1)
            )
            return ExecutionGrant.model_validate(row.payload) if row else None

    def revoke_grants(self, space_id: str, revoked_at) -> int:
        with session_scope() as session:
            rows = session.scalars(
                select(ExecutionGrantRow)
                .where(ExecutionGrantRow.space_id == space_id, ExecutionGrantRow.status == "active")
                .with_for_update()
            ).all()
            for row in rows:
                grant = ExecutionGrant.model_validate(row.payload)
                grant.status = "revoked"
                grant.revoked_at = revoked_at
                row.status = "revoked"
                row.payload = grant.model_dump(mode="json")
            return len(rows)

    def save_action_execution(self, execution: ActionExecution) -> None:
        with session_scope() as session:
            row = session.get(ActionExecutionRow, execution.action_id, with_for_update=True)
            if row is not None and row.status in ("completed", "failed", "rejected", "cancelled"):
                return
            if row is None:
                row = ActionExecutionRow(action_id=execution.action_id)
                session.add(row)
            row.owner_id = self.owner_id
            row.grant_id = execution.grant_id
            row.plan_id = execution.plan_id
            row.service_id = execution.service_id
            row.space_id = execution.space_id
            row.status = execution.status
            row.service_epoch = execution.service_epoch
            row.payload = execution.model_dump(mode="json")

    def get_action_execution(self, action_id: str) -> Optional[ActionExecution]:
        with session_scope() as session:
            row = session.get(ActionExecutionRow, action_id)
            return ActionExecution.model_validate(row.payload) if row else None

    def recent_action_executions(self, space_id: str) -> list[ActionExecution]:
        with session_scope() as session:
            rows = session.scalars(select(ActionExecutionRow).where(ActionExecutionRow.space_id == space_id)
                                   .order_by(ActionExecutionRow.updated_at.desc(), ActionExecutionRow.action_id.desc())
                                   .limit(200)).all()
            return [ActionExecution.model_validate(row.payload) for row in rows]

    def unresolved_action_executions(self) -> list[ActionExecution]:
        with session_scope() as session:
            rows = session.scalars(
                select(ActionExecutionRow).where(
                    ActionExecutionRow.status.in_(("dispatching", "accepted", "unknown"))
                )
            ).all()
            return [ActionExecution.model_validate(row.payload) for row in rows]

    def resolve_unknown_action(self, execution: ActionExecution, result: ActionResult,
                               recovery_token: Optional[str] = None) -> Optional[ActionExecution]:
        # Compare under a row lock. A duplicate reconciler cannot overwrite a terminal
        # result, and the action ledger + displayed plan result commit together.
        with session_scope() as session:
            row = session.get(ActionExecutionRow, execution.action_id, with_for_update=True)
            if row is None:
                return None
            if row.status != "unknown":
                return ActionExecution.model_validate(row.payload)
            if recovery_token is not None and row.recovery_token != recovery_token:
                return ActionExecution.model_validate(row.payload)
            current = ActionExecution.model_validate(row.payload)
            execution = execution.model_copy(update={"recovery_attempts": current.recovery_attempts,
                "last_checked_at": execution.completed_at, "next_check_at": None, "recovery_exhausted": False})
            row.status = execution.status
            row.payload = execution.model_dump(mode="json")
            row.recovery_token = row.recovery_until = None
            plan = session.get(PlanRow, execution.plan_id, with_for_update=True) if execution.plan_id else None
            from app.harness.reconciliation import reconciliation_activity
            if plan:
                present = any(item.get("action_id") == execution.action_id for item in plan.results)
                plan.results = [result.model_dump(mode="json") if item.get("action_id") == execution.action_id
                                and item.get("outcome") == "unknown" else item for item in plan.results]
                if not present:
                    plan.results = [*plan.results, result.model_dump(mode="json")]
            activity = reconciliation_activity(execution, result,
                                                execution.person_id or (plan.person_id if plan else None))
            session.add(ActivityRow(activity_id=activity.activity_id, space_id=activity.space_id,
                                    payload=activity.model_dump(mode="json")))
            return execution.model_copy(deep=True)

    # ---- activity ----

    def append_activity(self, record: ActivityRecord) -> None:
        with session_scope() as session:
            session.add(
                ActivityRow(
                    activity_id=record.activity_id,
                    space_id=record.space_id,
                    payload=record.model_dump(mode="json"),
                )
            )

    def activity(self, space_id: str, limit: int) -> list[ActivityRecord]:
        with session_scope() as session:
            rows = session.scalars(
                select(ActivityRow)
                .where(ActivityRow.space_id == space_id)
                .order_by(ActivityRow.seq.desc())
                .limit(limit)
            ).all()
            return [ActivityRecord.model_validate(row.payload) for row in rows]

    # ---- demo reset ----

    def clear(self) -> None:
        with session_scope() as session:
            space_ids = set(session.scalars(select(SpaceStateRow.space_id)).all())
            space_ids.update(session.scalars(select(PlanRow.space_id)).all())
            space_ids.update(session.scalars(select(ServiceRow.space_id)).all())
            session.query(ScheduledStepRow).delete()
            session.query(ServiceFlagRow).delete()
            session.query(PlanRow).delete()
            session.query(ServiceRow).delete()
            session.query(ActivityRow).delete()
            session.query(PendingClarificationRow).delete()
            session.query(ActionExecutionRow).delete()
            session.query(ExecutionGrantRow).delete()
            session.query(PolicyDecisionRow).delete()
            session.query(OutboxEventRow).delete()
            session.query(SharedSettingRow).delete()
            # Epochs only ever move forward, so requests still in flight stay invalid.
            for space_id in space_ids:
                row = session.get(SpaceStateRow, space_id)
                if row is None:
                    session.add(SpaceStateRow(space_id=space_id, epoch=1))
                else:
                    row.epoch += 1

    # ---- startup ----

    def loaded_summary(self) -> dict[str, int]:
        """What a restart recovered. Used by logs and tests, never by business rules."""
        with session_scope() as session:
            return {
                "plans": session.scalar(select(func.count()).select_from(PlanRow)) or 0,
                "services": session.scalar(select(func.count()).select_from(ServiceRow)) or 0,
                "activity": session.scalar(select(func.count()).select_from(ActivityRow)) or 0,
                "clarifications": session.scalar(select(func.count()).select_from(PendingClarificationRow)) or 0,
                "grants": session.scalar(select(func.count()).select_from(ExecutionGrantRow)) or 0,
                "actions": session.scalar(select(func.count()).select_from(ActionExecutionRow)) or 0,
            }

    def startup_reconcile(self, *, include_legacy: bool = True) -> dict[str, int]:
        """Resolve process-local work left behind by a crash without replaying an uncertain device action."""
        with session_scope() as session:
            active = session.scalar(select(func.count()).select_from(ServiceRow).where(ServiceRow.status == "active")) or 0
            from app.db.ownership import owner_is_gone
            owners = set()
            for table in (ServiceFlagRow, ScheduledStepRow, ActionExecutionRow):
                owners.update(session.scalars(select(table.owner_id).distinct()).all())
            gone = {owner for owner in owners if (include_legacy or owner is not None) and owner_is_gone(session, owner)}
            flags = session.scalars(select(ServiceFlagRow).with_for_update()).all()
            flags = [row for row in flags if row.owner_id in gone]
            running = session.scalars(
                select(ScheduledStepRow).where(ScheduledStepRow.status == "running").with_for_update()
            ).all()
            running = [row for row in running if row.owner_id in gone]
            for row in running:
                row.status = "cancelled"
                row.payload = {**row.payload, "status": "cancelled"}
            for row in flags:
                session.delete(row)
            unresolved = session.scalars(
                select(ActionExecutionRow)
                .where(ActionExecutionRow.status.in_(("pending", "dispatching", "accepted")))
                .with_for_update()
            ).all()
            unresolved = [row for row in unresolved if row.owner_id in gone]
            for row in unresolved:
                payload = dict(row.payload)
                payload["status"] = "cancelled" if row.status == "pending" else "unknown"
                payload["error_kind"] = "restart_reconciliation"
                payload["error_detail"] = ("发送前执行进程已退出，动作已取消" if row.status == "pending"
                                           else "执行进程退出时设备最终结果不可确定，需通过 actionId 向网关对账")
                row.status = payload["status"]
                row.payload = payload
            unknown_actions = session.scalar(
                select(func.count()).select_from(ActionExecutionRow).where(ActionExecutionRow.status == "unknown")
            ) or 0
            return {
                "active_services": int(active),
                "cancelled_unknown_steps": len(running),
                "cleared_inflight_flags": len(flags),
                "unknown_actions": int(unknown_actions),
            }

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

from app.contracts import ActionResult, ActivityRecord, Plan, ScheduledStep, Service
from app.db.models import ActivityRow, PlanRow, ScheduledStepRow, ServiceFlagRow, ServiceRow, SpaceStateRow
from app.db.session import session_scope
from app.repositories.store import PlanRecord


def _service_from_row(row: ServiceRow, steps: list[ScheduledStepRow]) -> Service:
    payload = dict(row.payload)
    payload["schedule"] = [step.payload for step in sorted(steps, key=lambda s: s.ordinal)]
    return Service.model_validate(payload)


class SqlStore:
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

    def save_plan(self, record: PlanRecord) -> None:
        plan = record.plan
        with session_scope() as session:
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

    def save_service(self, service: Service) -> None:
        with session_scope() as session:
            row = session.get(ServiceRow, service.service_id)
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
            session.add(ServiceFlagRow(service_id=service_id, flag=flag))
            return True

    def release_flag(self, service_id: str, flag: str) -> None:
        with session_scope() as session:
            row = session.get(ServiceFlagRow, (service_id, flag))
            if row is not None:
                session.delete(row)

    def has_flag(self, service_id: str, flag: str) -> bool:
        with session_scope() as session:
            return session.get(ServiceFlagRow, (service_id, flag)) is not None

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
            }

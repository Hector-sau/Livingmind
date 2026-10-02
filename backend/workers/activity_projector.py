"""Consumer: turns delivered domain events into a per-service summary.

Idempotent by construction: a row in ``consumer_receipts`` is written in the same transaction
as the projection update, so a re-delivered event changes nothing the second time.
The activity log the app shows is NOT built here — it is written synchronously by the API.
This projection is the audit/analytics view on top of it.
"""

from __future__ import annotations

import time
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import aliased

from app.db.models import ConsumerReceiptRow, DomainEventRow, ServiceProjectionRow
from app.db.session import session_scope
from app.events.envelope import Envelope

CONSUMER = "activity-projector"


def _apply(session, envelope: Envelope) -> None:
    aggregate = envelope.aggregate_id
    row = session.get(ServiceProjectionRow, aggregate)
    if row is None:
        row = ServiceProjectionRow(
            service_id=aggregate,
            space_id=envelope.space_id,
            person_id=envelope.person_id,
            status="unknown",
            adjustments=0,
            device_actions=0,
            events_applied=0,
        )
        session.add(row)
    if envelope.event_type == "service.started":
        # A delayed or redelivered start must never resurrect a terminal service.
        if row.status == "unknown":
            row.status = "active"
    elif envelope.event_type == "service.adjusted":
        row.adjustments += 1
    elif envelope.event_type in ("service.stopped", "service.completed", "service.failed"):
        if row.status not in ("stopped", "completed", "failed"):
            row.status = envelope.event_type.split(".", 1)[1]
    elif envelope.event_type == "device.action.completed":
        row.device_actions += 1
    row.person_id = row.person_id or envelope.person_id
    row.events_applied += 1


def consume_once(batch_size: int = 100) -> dict[str, int]:
    """Project at most ``batch_size`` events without skipping earlier same-space rows.

    A second consumer cannot leap past a locked earlier event in the same space.
    Different spaces can progress independently. Receipts and projection commit together.
    """
    totals = {"read": 0, "applied": 0}
    if batch_size <= 0:
        return totals
    while totals["read"] < batch_size:
        with session_scope() as session:
            seen = select(ConsumerReceiptRow.event_id).where(ConsumerReceiptRow.consumer == CONSUMER)
            prior = aliased(DomainEventRow)
            earlier_unseen = (
                select(prior.seq)
                .where(prior.space_id == DomainEventRow.space_id,
                       prior.seq < DomainEventRow.seq,
                       prior.event_id.not_in(seen))
                .exists()
            )
            rows = session.scalars(
                select(DomainEventRow)
                .where(DomainEventRow.event_id.not_in(seen), ~earlier_unseen)
                .order_by(DomainEventRow.seq)
                .limit(batch_size - totals["read"])
                .with_for_update(skip_locked=True)
            ).all()
            if not rows:
                break
            for row in rows:
                envelope = Envelope.model_validate(row.payload)
                _apply(session, envelope)
                session.add(ConsumerReceiptRow(consumer=CONSUMER, event_id=envelope.event_id))
            totals["read"] += len(rows)
            totals["applied"] += len(rows)
    return totals


def run(poll_seconds: float = 1.0, iterations: Optional[int] = None) -> None:
    count = 0
    while iterations is None or count < iterations:
        consume_once()
        count += 1
        time.sleep(poll_seconds)


if __name__ == "__main__":  # pragma: no cover - entry point for the compose service
    run()

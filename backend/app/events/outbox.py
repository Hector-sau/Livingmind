"""Outbox reader/writer.

The write side is part of the store transaction (see ``Store.save_service(..., events=...)``).
This module only deals with what happens afterwards: claiming pending rows, marking them
published, and recording failures without losing anything.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import aliased

from app.db.models import OutboxEventRow
from app.db.session import session_scope
from app.events.envelope import Envelope
from app.events.publisher import EventPublisher

MAX_ATTEMPTS = 5


def pending_count() -> int:
    with session_scope() as session:
        rows = session.scalars(select(OutboxEventRow.event_id).where(OutboxEventRow.published_at.is_(None))).all()
        return len(rows)


def publish_pending(publisher: EventPublisher, batch_size: int = 50) -> dict[str, int]:
    """Publish at most ``batch_size`` events, serializing pending rows per space.

    SKIP LOCKED alone allows a competing worker to jump past a locked earlier event.
    The NOT EXISTS predicate excludes later rows while any earlier row in that space
    is still unpublished, including a dead letter. At most one row per space is
    claimed per transaction; the outer loop preserves the old batch API.
    """
    totals = {"claimed": 0, "published": 0, "failed": 0}
    if batch_size <= 0:
        return totals
    while totals["claimed"] < batch_size:
        prior = aliased(OutboxEventRow)
        earlier_pending = (
            select(prior.event_id)
            .where(prior.space_id == OutboxEventRow.space_id,
                   prior.seq < OutboxEventRow.seq,
                   prior.published_at.is_(None))
            .exists()
        )
        with session_scope() as session:
            rows = session.scalars(
                select(OutboxEventRow)
                .where(OutboxEventRow.published_at.is_(None),
                       OutboxEventRow.attempts < MAX_ATTEMPTS,
                       ~earlier_pending)
                .order_by(OutboxEventRow.seq)
                .limit(batch_size - totals["claimed"])
                .with_for_update(skip_locked=True)
            ).all()
            if not rows:
                break
            envelopes = [Envelope.model_validate(row.payload) for row in rows]
            try:
                delivered = set(publisher.publish(envelopes))
                error: Optional[str] = None
            except Exception as exc:  # the bus is down: keep every row, try again later
                delivered, error = set(), f"{type(exc).__name__}: {exc}"[:500]
            now = datetime.now(timezone.utc)
            for row in rows:
                row.attempts += 1
                if row.event_id in delivered:
                    row.published_at = now
                    row.last_error = None
                    totals["published"] += 1
                else:
                    row.last_error = error
                    totals["failed"] += 1
            totals["claimed"] += len(rows)
        if totals["failed"]:
            break  # do not retry the same failed row in this pass
    return totals


def dead_letters() -> list[Envelope]:
    """Events that failed too often. They are kept, never dropped, and need a human."""
    with session_scope() as session:
        rows = session.scalars(
            select(OutboxEventRow).where(
                OutboxEventRow.published_at.is_(None), OutboxEventRow.attempts >= MAX_ATTEMPTS
            )
        ).all()
        return [Envelope.model_validate(row.payload) for row in rows]


def retry_dead_letter(event_id: str) -> bool:
    """Explicit operator action; never silently discard or automatically skip a poison event."""
    with session_scope() as session:
        row = session.get(OutboxEventRow, event_id, with_for_update=True)
        if row is None or row.published_at is not None or row.attempts < MAX_ATTEMPTS:
            return False
        row.attempts = 0
        row.last_error = None
        return True

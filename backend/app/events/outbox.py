"""Outbox reader/writer.

The write side is part of the store transaction (see ``Store.save_service(..., events=...)``).
This module only deals with what happens afterwards: claiming pending rows, marking them
published, and recording failures without losing anything.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select

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
    """One publisher pass. Safe to run in several processes at once.

    Rows are claimed with FOR UPDATE SKIP LOCKED, so two publishers never fight over the same
    event; per space the oldest event is always claimed first, which keeps space ordering.
    """
    with session_scope() as session:
        rows = session.scalars(
            select(OutboxEventRow)
            .where(OutboxEventRow.published_at.is_(None), OutboxEventRow.attempts < MAX_ATTEMPTS)
            .order_by(OutboxEventRow.created_at, OutboxEventRow.event_id)
            .limit(batch_size)
            .with_for_update(skip_locked=True)
        ).all()
        if not rows:
            return {"claimed": 0, "published": 0, "failed": 0}
        envelopes = [Envelope.model_validate(row.payload) for row in rows]
        try:
            delivered = set(publisher.publish(envelopes))
            error: Optional[str] = None
        except Exception as exc:  # the bus is down: keep every row, try again later
            delivered, error = set(), f"{type(exc).__name__}: {exc}"[:500]
        now = datetime.now(timezone.utc)
        published = 0
        for row in rows:
            row.attempts += 1
            if row.event_id in delivered:
                row.published_at = now
                row.last_error = None
                published += 1
            else:
                row.last_error = error
        return {"claimed": len(rows), "published": published, "failed": len(rows) - published}


def dead_letters() -> list[Envelope]:
    """Events that failed too often. They are kept, never dropped, and need a human."""
    with session_scope() as session:
        rows = session.scalars(
            select(OutboxEventRow).where(
                OutboxEventRow.published_at.is_(None), OutboxEventRow.attempts >= MAX_ATTEMPTS
            )
        ).all()
        return [Envelope.model_validate(row.payload) for row in rows]

"""Publishing side of the transactional outbox.

``EventPublisher`` is the seam. The shipped implementation delivers into a PostgreSQL table
(``domain_events``), which costs nothing extra to run and still exercises everything that
matters: at-least-once delivery, retries, ordering per space, competing consumers with
``FOR UPDATE SKIP LOCKED`` and ``event_id`` de-duplication.

A Kafka implementation would be a second class here (same protocol, message key = spaceId).
It is deliberately not written yet: there is no broker to verify it against, and an untested
publisher in the repository would be worse than none. See docs/technology-architecture.md.
"""

from __future__ import annotations

from typing import Protocol

from sqlalchemy.dialects.postgresql import insert

from app.db.models import DomainEventRow
from app.db.session import session_scope
from app.events.envelope import Envelope


class EventPublisher(Protocol):
    name: str

    def publish(self, events: list[Envelope]) -> list[str]:
        """Deliver the events. Returns the ids actually delivered (at-least-once)."""
        ...


class PostgresQueuePublisher:
    """Delivers into ``domain_events``; consumers poll that table."""

    name = "postgres-queue"

    def publish(self, events: list[Envelope]) -> list[str]:
        if not events:
            return []
        with session_scope() as session:
            for envelope in events:
                # A re-published event must not create a second delivery row.
                statement = (
                    insert(DomainEventRow)
                    .values(
                        event_id=envelope.event_id,
                        event_type=envelope.event_type,
                        space_id=envelope.space_id,
                        payload=envelope.model_dump(mode="json", by_alias=True),
                    )
                    .on_conflict_do_nothing(index_elements=[DomainEventRow.event_id])
                )
                session.execute(statement)
        return [e.event_id for e in events]


class FailingPublisher:
    """Used by tests (and by a demo of an outage): the bus is down, events stay pending."""

    name = "failing"

    def __init__(self, error: str = "bus unavailable"):
        self.error = error

    def publish(self, events: list[Envelope]) -> list[str]:
        raise RuntimeError(self.error)

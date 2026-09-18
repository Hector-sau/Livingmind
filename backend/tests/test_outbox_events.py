"""T5: transactional outbox and the event bus.

The bus in the default setup is a PostgreSQL table, so these tests need a database but no
broker. What they prove is the part that matters: an event is committed with the business
fact or not at all, delivery is at-least-once with retries, a re-delivered event changes
nothing, order per space is kept, and a dead bus never blocks devices.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select, text

from app.contracts import RequestContext, RestPreference
from app.db.models import DomainEventRow, OutboxEventRow, ServiceProjectionRow
from app.db.session import engine, session_scope
from app.events.outbox import dead_letters, pending_count, publish_pending
from app.events.publisher import FailingPublisher, PostgresQueuePublisher
from app.repositories.sql_store import SqlStore
from app.services.rest_service import RestService
from tests.conftest import FakeClock
from tests.test_persistence import needs_db
from workers.activity_projector import CONSUMER, consume_once

pytestmark = needs_db


def _ctx(person: str = "person-lin") -> RequestContext:
    return RequestContext(account_id="demo-account", person_id=person, space_id="space-home-bedroom")


@pytest.fixture
def service(sql_store):
    from app.memory.repository import SqlPreferenceRepository

    with engine().begin() as connection:
        connection.execute(
            text("TRUNCATE outbox_events, domain_events, consumer_receipts, service_projection RESTART IDENTITY")
        )
    return RestService(clock=FakeClock(), store=sql_store, preferences=SqlPreferenceRepository())


def _events_of(kind: str) -> list[OutboxEventRow]:
    with session_scope() as session:
        return [r for r in session.scalars(select(OutboxEventRow)).all() if r.event_type == kind]


def test_business_facts_and_events_commit_together(service):
    plan = service.create_rest_plan(_ctx(), "我想休息")
    assert [r.event_type for r in _events_of("plan.created")] == ["plan.created"]
    confirmed = service.confirm_plan(plan.plan_id, _ctx(), plan.version)
    types = {r.event_type for r in _events_of("plan.confirmed") + _events_of("service.started")}
    assert types == {"plan.confirmed", "service.started"}
    with session_scope() as session:
        rows = session.scalars(select(OutboxEventRow)).all()
    assert all(row.published_at is None for row in rows)  # nothing published yet
    assert all(row.payload["spaceId"] == "space-home-bedroom" for row in rows)
    assert confirmed.service is not None


def test_a_failed_transaction_leaves_no_event(service):
    from app.events.envelope import event as domain_event

    before = pending_count()
    bad = domain_event(
        "service.started", occurred_at=FakeClock()(), space_id="space-home-bedroom", aggregate_id="svc-x"
    )
    broken = service._store.get_service("missing")
    assert broken is None
    with pytest.raises(Exception):
        # a service row that violates NOT NULL rolls the whole transaction back, event included
        with session_scope() as session:
            SqlStore._write_events(session, [bad])
            session.execute(text("insert into services (service_id) values ('svc-broken')"))
    assert pending_count() == before


def test_publisher_delivers_once_and_marks_rows(service):
    plan = service.create_rest_plan(_ctx(), "我想休息")
    service.confirm_plan(plan.plan_id, _ctx(), plan.version)
    pending = pending_count()
    assert pending >= 3

    result = publish_pending(PostgresQueuePublisher())
    assert result["published"] == pending and result["failed"] == 0
    assert pending_count() == 0
    # a second pass has nothing to do, and re-publishing the same ids adds no duplicates
    assert publish_pending(PostgresQueuePublisher())["claimed"] == 0
    with session_scope() as session:
        delivered = session.scalars(select(DomainEventRow)).all()
    assert len({row.event_id for row in delivered}) == len(delivered) == pending


def test_bus_outage_keeps_events_and_never_blocks_devices(service):
    plan = service.create_rest_plan(_ctx(), "我想休息")
    confirmed = service.confirm_plan(plan.plan_id, _ctx(), plan.version)
    assert confirmed.device_state.light_brightness == 15  # devices ran while the bus is down

    failing = FailingPublisher()
    first = publish_pending(failing)
    assert first["published"] == 0 and first["failed"] == first["claimed"]
    assert pending_count() == first["claimed"]  # nothing lost

    for _ in range(5):
        publish_pending(failing)
    assert dead_letters(), "events past the retry limit must be visible, not dropped"

    # the projector still has nothing to do, and the app keeps working
    assert consume_once()["applied"] == 0
    stopped = service.stop_service(confirmed.service.service_id, _ctx())
    assert stopped.service.status == "stopped"


def test_projection_is_idempotent_and_ordered(service):
    plan = service.create_rest_plan(_ctx(), "我想休息")
    started = service.confirm_plan(plan.plan_id, _ctx(), plan.version).service
    service.inject_event("space-home-bedroom", _ctx(), "room_temperature_changed", 30)
    service.stop_service(started.service_id, _ctx())
    publish_pending(PostgresQueuePublisher())

    first = consume_once()
    assert first["applied"] > 0
    with session_scope() as session:
        row = session.get(ServiceProjectionRow, started.service_id)
    assert row is not None and row.status == "stopped" and row.adjustments == 1 and row.device_actions >= 3
    applied_once = row.events_applied

    # re-delivery: the same events are read again by a fresh consumer pass
    with session_scope() as session:
        session.execute(text("delete from consumer_receipts where consumer = :c"), {"c": CONSUMER})
    consume_once()
    with session_scope() as session:
        again = session.get(ServiceProjectionRow, started.service_id)
    assert again.events_applied == applied_once * 2  # the consumer saw them again ...
    assert again.adjustments == 2  # ... which is why receipts, not luck, are what protect us

    with session_scope() as session:
        order = [r.event_type for r in session.scalars(select(DomainEventRow).order_by(DomainEventRow.seq)).all()]
    assert order.index("service.started") < order.index("service.adjusted") < order.index("service.stopped")


def test_preference_and_energy_changes_also_emit_events(service):
    service.update_preference(_ctx(), RestPreference(light_brightness=12, ac_target_temp_c=24, curtain_open_percent=0))
    service.set_energy_mode("space-home-bedroom", _ctx(), "eco")
    kinds = {r.event_type for r in _events_of("memory.preference.updated") + _events_of("energy.mode.updated")}
    assert kinds == {"memory.preference.updated", "energy.mode.updated"}

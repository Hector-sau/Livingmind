"""T2: person preferences survive a restart when PostgreSQL is configured.

The SQL tests only run when LIVINGMIND_TEST_DATABASE_URL points at a disposable database:
    LIVINGMIND_TEST_DATABASE_URL=postgresql+psycopg://user:pw@127.0.0.1:5432/livingmind pytest
Without it they are skipped and the demo keeps running fully in memory.
"""

import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app import config
from app.contracts import RestPreference
from app.db import session as db_session
from app.memory.repository import InMemoryPreferenceRepository, SqlPreferenceRepository
from app.memory.service import MemoryService
from app.services.rest_service import RestService
from tests.conftest import FakeClock

BACKEND = Path(__file__).resolve().parent.parent
TEST_DB_URL = os.getenv("LIVINGMIND_TEST_DATABASE_URL", "").strip()
needs_db = pytest.mark.skipif(not TEST_DB_URL, reason="LIVINGMIND_TEST_DATABASE_URL is not set")


@pytest.fixture
def sql_repo():
    """A migrated, empty person_preferences table pointed at the test database."""
    from alembic import command
    from alembic.config import Config

    previous = config.DATABASE_URL
    config.DATABASE_URL = TEST_DB_URL
    db_session.reset_engine()
    alembic_cfg = Config(str(BACKEND / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    alembic_cfg.set_main_option("sqlalchemy.url", TEST_DB_URL)
    command.upgrade(alembic_cfg, "head")
    repo = SqlPreferenceRepository()
    repo.clear()
    try:
        yield repo
    finally:
        repo.clear()
        db_session.reset_engine()
        config.DATABASE_URL = previous


@pytest.fixture(params=["memory", "sql"])
def repo(request):
    """The same contract has to hold for both implementations."""
    if request.param == "memory":
        yield InMemoryPreferenceRepository()
    else:
        if not TEST_DB_URL:
            pytest.skip("LIVINGMIND_TEST_DATABASE_URL is not set")
        yield request.getfixturevalue("sql_repo")


PREF = RestPreference(light_brightness=20, ac_target_temp_c=24.5, curtain_open_percent=10)


def test_repository_contract_round_trip(repo):
    assert repo.get("person-lin") is None
    repo.put("person-lin", PREF, None)
    stored = repo.get("person-lin")
    assert stored is not None
    assert stored.preference == PREF and stored.updated_at is None

    edited_at = datetime(2026, 9, 18, 10, 30, tzinfo=timezone.utc)
    repo.put("person-lin", PREF.model_copy(update={"ac_target_temp_c": 26.0}), edited_at)
    stored = repo.get("person-lin")
    assert stored.preference.ac_target_temp_c == 26.0
    assert stored.updated_at == edited_at
    assert repo.get("person-chen") is None  # one person's edit never leaks to another

    repo.clear()
    assert repo.get("person-lin") is None


def test_memory_service_seeds_without_overwriting_edits(repo):
    clock = FakeClock()
    memory = MemoryService(clock, repo)
    assert memory.preference("person-lin").ac_target_temp_c == 25  # seeded
    assert memory.view("person-lin", "space-home-bedroom").updated_at is None

    memory.update("person-lin", PREF)
    # A second service over the same store (a restart) must not re-seed over the edit.
    again = MemoryService(FakeClock(), repo)
    assert again.preference("person-lin") == PREF
    assert again.view("person-lin", "space-home-bedroom").updated_at == clock.now
    assert again.preference("person-chen").ac_target_temp_c == 22  # untouched seed


@needs_db
def test_preferences_survive_a_backend_restart(sql_repo):
    clock = FakeClock()
    service = RestService(clock=clock, preferences=sql_repo)
    service.update_preference(_ctx(), RestPreference(light_brightness=10, ac_target_temp_c=23, curtain_open_percent=5))
    # A brand new service instance stands in for "the process was restarted".
    restarted = RestService(clock=FakeClock(), preferences=SqlPreferenceRepository())
    view = restarted.memory_view(_ctx())
    assert view.preference.ac_target_temp_c == 23
    assert view.updated_at is not None
    # In-memory facts (plans, services, activity) are still process-local in T2.1.
    assert restarted.bootstrap("demo-account").active_service is None


@needs_db
def test_demo_reset_restores_seeded_preferences(sql_repo):
    service = RestService(clock=FakeClock(), preferences=sql_repo)
    service.update_preference(_ctx(), RestPreference(light_brightness=10, ac_target_temp_c=23, curtain_open_percent=5))
    service.reset("demo-account")
    view = RestService(clock=FakeClock(), preferences=SqlPreferenceRepository()).memory_view(_ctx())
    assert view.preference.ac_target_temp_c == 25 and view.updated_at is None


@needs_db
def test_api_uses_the_database_when_configured(sql_repo):
    """With LIVINGMIND_DATABASE_URL set, a plain RestService() picks the SQL repository."""
    from fastapi.testclient import TestClient

    from app.main import create_app
    from app.services.rest_service import get_rest_service

    service = RestService(clock=FakeClock())  # no repository argument on purpose
    app = create_app()
    app.dependency_overrides[get_rest_service] = lambda: service
    client = TestClient(app)
    body = {"context": _ctx().model_dump(by_alias=True), "preference": {"lightBrightness": 12, "acTargetTempC": 23.5, "curtainOpenPercent": 0}}
    assert client.put("/api/memory/preference", json=body).status_code == 200

    restarted = RestService(clock=FakeClock())
    assert restarted.memory_view(_ctx()).preference.ac_target_temp_c == 23.5
    # the rest loop still works on top of the persisted preference
    plan = client.post("/api/plans/rest", json={"context": _ctx().model_dump(by_alias=True), "utterance": "我想休息"}).json()
    assert any(a["device"] == "ac" and a["value"] == 23.5 for a in plan["actions"])


def _ctx():
    from app.contracts import RequestContext

    return RequestContext(**{"accountId": "demo-account", "personId": "person-lin", "spaceId": "space-home-bedroom"})


# ---- T2.2: plans, services, overnight steps and activity on PostgreSQL ----


@pytest.fixture
def sql_store(sql_repo):
    """A migrated, empty business-fact store (reuses the migration from sql_repo)."""
    from sqlalchemy import text

    from app.db.session import engine
    from app.repositories.sql_store import SqlStore

    with engine().begin() as connection:
        connection.execute(
            text(
                "TRUNCATE plans, services, scheduled_steps, service_flags, "
                "activity_records, space_state RESTART IDENTITY"
            )
        )
    return SqlStore()


@needs_db
def test_plans_services_steps_and_activity_survive_a_restart(sql_store):
    clock = FakeClock()
    service = RestService(clock=clock, store=sql_store, preferences=SqlPreferenceRepository())
    plan = service.create_rest_plan(_ctx(), "我想休息")
    confirmed = service.confirm_plan(plan.plan_id, _ctx(), plan.version)
    service_id = confirmed.service.service_id
    service.advance_clock(service_id, _ctx(), None)  # run the 23:00 step

    # New process, same database.
    from app.repositories.sql_store import SqlStore

    restarted = RestService(clock=FakeClock(), store=SqlStore(), preferences=SqlPreferenceRepository())
    recovered = restarted.bootstrap("demo-account").active_service
    assert recovered is not None and recovered.service_id == service_id
    assert recovered.night_clock == "23:00"
    assert [s.status for s in recovered.schedule][:2] == ["done", "pending"]
    kinds = [a.kind for a in restarted.activity("demo-account", "space-home-bedroom", 50)]
    assert "plan_confirmed" in kinds and "schedule_step_executed" in kinds
    # the recovered service can still be stopped by the new process
    stopped = restarted.stop_service(service_id, _ctx())
    assert stopped.service.status == "stopped"
    assert all(s.status in ("done", "cancelled") for s in stopped.service.schedule)


@needs_db
def test_database_refuses_a_second_active_service_in_one_space(sql_store):
    from sqlalchemy.exc import IntegrityError

    service = RestService(clock=FakeClock(), store=sql_store, preferences=SqlPreferenceRepository())
    plan = service.create_rest_plan(_ctx(), "我想休息")
    first = service.confirm_plan(plan.plan_id, _ctx(), plan.version).service
    assert first is not None

    # Bypass the service layer on purpose: the constraint must hold in the database itself.
    clone = first.model_copy(update={"service_id": "svc-duplicate"})
    with pytest.raises(IntegrityError):
        sql_store.save_service(clone)


@needs_db
def test_a_night_step_is_claimed_by_exactly_one_caller(sql_store):
    import threading

    from app.repositories.sql_store import SqlStore

    service = RestService(clock=FakeClock(), store=sql_store, preferences=SqlPreferenceRepository())
    plan = service.create_rest_plan(_ctx(), "我想休息")
    started = service.confirm_plan(plan.plan_id, _ctx(), plan.version).service
    step_ids = [s.step_id for s in started.schedule]

    claims: list[list[str]] = []
    barrier = threading.Barrier(2)

    def claim() -> None:
        store = SqlStore()  # its own connection, like a second API instance
        barrier.wait(timeout=5)
        claims.append(store.claim_steps(started.service_id, step_ids))

    threads = [threading.Thread(target=claim) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    claimed = [step for result in claims for step in result]
    assert sorted(claimed) == sorted(step_ids)  # every step claimed
    assert len(claimed) == len(set(claimed))  # and never twice

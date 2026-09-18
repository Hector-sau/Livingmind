"""Shared fixtures.

The whole suite can run against either store. Point it at a disposable database to run
every test on PostgreSQL instead of process memory:

    LIVINGMIND_TEST_STORE=sql \
    LIVINGMIND_TEST_DATABASE_URL=postgresql+psycopg://livingmind:livingmind@127.0.0.1:5432/livingmind \
    pytest
"""

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.services.rest_service import RestService, get_rest_service

BACKEND = Path(__file__).resolve().parent.parent
TEST_DB_URL = os.getenv("LIVINGMIND_TEST_DATABASE_URL", "").strip()
SQL_STORE = os.getenv("LIVINGMIND_TEST_STORE", "").strip() == "sql"


def sql_mode() -> bool:
    return SQL_STORE and bool(TEST_DB_URL)


def migrate_test_database() -> None:
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    cfg.set_main_option("sqlalchemy.url", TEST_DB_URL)
    command.upgrade(cfg, "head")


def truncate_test_database() -> None:
    from sqlalchemy import text

    from app.db.session import engine

    with engine().begin() as connection:
        connection.execute(
            text(
                "TRUNCATE plans, services, scheduled_steps, service_flags, "
                "activity_records, space_state, person_preferences RESTART IDENTITY"
            )
        )
        connection.execute(text("ALTER SEQUENCE livingmind_id_seq RESTART WITH 1"))


@pytest.fixture(autouse=True)
def _store_backend(monkeypatch):
    """In SQL mode every test starts from a migrated, empty database."""
    if not sql_mode():
        yield None
        return
    from app import config as app_config
    from app.db import session as db_session

    monkeypatch.setattr(app_config, "DATABASE_URL", TEST_DB_URL)
    db_session.reset_engine()
    migrate_test_database()
    truncate_test_database()
    try:
        yield "sql"
    finally:
        db_session.reset_engine()


class FakeClock:
    def __init__(self):
        self.now = datetime(2026, 9, 17, 12, 0, tzinfo=timezone.utc)

    def __call__(self):
        return self.now

    def advance(self, **kw):
        self.now += timedelta(**kw)


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def service(clock):
    return RestService(clock=clock)


@pytest.fixture
def client(service):
    app = create_app()
    app.dependency_overrides[get_rest_service] = lambda: service
    return TestClient(app)


def ctx(person="person-lin", account="demo-account", space="space-home-bedroom"):
    return {"accountId": account, "personId": person, "spaceId": space}


# ---- database fixtures shared by the persistence and event tests ----


@pytest.fixture
def sql_repo():
    """A migrated, empty person_preferences table pointed at the test database."""
    if not TEST_DB_URL:
        pytest.skip("LIVINGMIND_TEST_DATABASE_URL is not set")
    from app import config
    from app.db import session as db_session
    from app.memory.repository import SqlPreferenceRepository

    previous = config.DATABASE_URL
    config.DATABASE_URL = TEST_DB_URL
    db_session.reset_engine()
    migrate_test_database()
    repo = SqlPreferenceRepository()
    repo.clear()
    try:
        yield repo
    finally:
        repo.clear()
        db_session.reset_engine()
        config.DATABASE_URL = previous


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

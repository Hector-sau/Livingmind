from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.services.rest_service import RestService, get_rest_service


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

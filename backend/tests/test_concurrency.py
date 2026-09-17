"""Step B: a stop request must be able to preempt a batch that is mid-execution on a slow device."""

import threading

import pytest
from fastapi.testclient import TestClient

from app.adapters.virtual.devices import VirtualDeviceAdapter
from app.demo import seed
from app.main import create_app
from app.services.rest_service import RestService, get_rest_service
from tests.conftest import FakeClock, ctx

SPACE = "space-home-bedroom"


class SlowAdapter(VirtualDeviceAdapter):
    """Blocks the first write until the test releases it, so a stop can land mid-batch."""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.first_write_started = threading.Event()
        self.release = threading.Event()
        self._writes = 0

    def _before_write(self, device, command, value):
        self._writes += 1
        if self._writes == 1:
            self.first_write_started.set()
            assert self.release.wait(timeout=5), "test did not release the slow device"


def slow_service():
    svc = RestService(clock=FakeClock())
    adapter = SlowAdapter(SPACE, seed.INITIAL_DEVICE_STATE, svc._clock)
    svc._devices[SPACE] = adapter
    return svc, adapter


def test_stop_preempts_running_batch_on_slow_device():
    svc, adapter = slow_service()
    from app.contracts import RequestContext

    rc = RequestContext(**ctx())
    plan = svc.create_rest_plan(rc, "我想休息")

    outcome = {}

    def run_confirm():
        outcome["confirm"] = svc.confirm_plan(plan.plan_id, rc, plan.version)

    t = threading.Thread(target=run_confirm)
    t.start()
    assert adapter.first_write_started.wait(timeout=5)

    # While the first device write is still in flight, stop must not be blocked by the service lock.
    stop_done = threading.Event()
    stop_result = {}

    def run_stop():
        service_id = svc._store.active_service(SPACE).service_id
        stop_result["res"] = svc.stop_service(service_id, rc)
        stop_done.set()

    threading.Thread(target=run_stop).start()
    assert stop_done.wait(timeout=2), "stop was blocked while a device write was in progress"
    assert stop_result["res"].service.status == "stopped"

    adapter.release.set()
    t.join(timeout=5)
    assert not t.is_alive()

    results = outcome["confirm"].results
    # First action had already started and completes; the remaining ones are skipped by the guard.
    assert [r.outcome for r in results] == ["succeeded", "skipped", "skipped"]
    assert results[1].reason in ("服务已停止", "计划版本已失效")
    state = adapter.read_state()
    assert state.version == 1
    assert state.light_brightness == 15 and state.ac_target_temp_c == 26.0 and state.curtain_open_percent == 100


def test_stop_preempts_over_http_with_threadpool():
    """Same scenario through FastAPI: sync endpoints run in a threadpool, so two requests overlap."""
    svc, adapter = slow_service()
    app = create_app()
    app.dependency_overrides[get_rest_service] = lambda: svc
    client = TestClient(app)

    plan = client.post("/api/plans/rest", json={"context": ctx(), "utterance": "我想休息"}).json()
    confirm_res = {}

    def run_confirm():
        confirm_res["res"] = client.post(
            f"/api/plans/{plan['planId']}/confirm", json={"context": ctx(), "planVersion": 1}
        )

    t = threading.Thread(target=run_confirm)
    t.start()
    assert adapter.first_write_started.wait(timeout=5)

    boot = client.get("/api/bootstrap", params={"accountId": "demo-account"}).json()
    service_id = boot["activeService"]["serviceId"]
    stop = client.post(f"/api/services/{service_id}/stop", json={"context": ctx()})
    assert stop.status_code == 200 and stop.json()["service"]["status"] == "stopped"

    adapter.release.set()
    t.join(timeout=5)
    body = confirm_res["res"].json()
    assert [r["outcome"] for r in body["results"]] == ["succeeded", "skipped", "skipped"]
    assert body["deviceState"]["version"] == 1

    kinds = [i["kind"] for i in client.get(f"/api/spaces/{SPACE}/activity", params={"accountId": "demo-account"}).json()["items"]]
    assert kinds.count("action_executed") == 1 and kinds.count("action_rejected") == 2


def test_plan_started_before_stop_is_invalidated_when_slow_planning_returns():
    """A delayed agent response must not create a fresh confirmable plan after stop."""
    svc = RestService(clock=FakeClock())
    from app.contracts import RequestContext

    rc = RequestContext(**ctx())
    running_plan = svc.create_rest_plan(rc, "我想休息")
    running = svc.confirm_plan(running_plan.plan_id, rc, running_plan.version).service
    assert running is not None

    original = svc._agent.handle
    started, release = threading.Event(), threading.Event()

    def delayed(*args, **kwargs):
        started.set()
        assert release.wait(timeout=5), "test did not release planner"
        return original(*args, **kwargs)

    svc._agent.handle = delayed
    outcome = {}
    t = threading.Thread(target=lambda: outcome.setdefault("plan", svc.create_rest_plan(rc, "我想休息")))
    t.start()
    assert started.wait(timeout=5)
    svc.stop_service(running.service_id, rc)
    release.set()
    t.join(timeout=5)

    stale = outcome["plan"]
    assert stale.status == "invalidated"
    with pytest.raises(Exception) as exc:
        svc.confirm_plan(stale.plan_id, rc, stale.version)
    assert getattr(exc.value, "code", None) == "PLAN_INVALIDATED"

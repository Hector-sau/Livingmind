"""Two OS processes share SQL, optional Redis, and one independent virtual gateway.

Unlike thread-only tests, the gateway's receipts/device state live in a manager process;
each API worker holds only a proxy. Run with LIVINGMIND_TEST_STORE=sql and a disposable DB.
This is still a virtual device, not a SpaceMind integration.
"""

from __future__ import annotations

import multiprocessing as mp
import os
import select
import socket
import socketserver
import time
from threading import Event, Thread
from multiprocessing.managers import BaseManager
from urllib.parse import urlsplit, urlunsplit

import pytest

from app.adapters.gateway import AdapterDeviceGateway
from app.adapters.protocol import DeviceCommandRequest
from app.adapters.virtual.devices import VirtualDeviceAdapter
from app.clock import utc_now
from app.contracts import RequestContext
from app.demo import seed
from app.memory.repository import SqlPreferenceRepository
from app.repositories.sql_store import SqlStore
from app.services.rest_service import RestService
from tests.test_persistence import needs_db
from tests.test_cache_coordination import needs_redis

pytestmark = needs_db
SPACE = "space-home-bedroom"


class ControlledVirtualAdapter(VirtualDeviceAdapter):
    def __init__(self):
        super().__init__(SPACE, seed.INITIAL_DEVICE_STATE, utc_now)
        self.block_next = False
        self.entered = Event()
        self.release = Event()

    def _before_write(self, device, command, value):
        if self.block_next:
            self.block_next = False
            self.entered.set()
            assert self.release.wait(15)


class SharedHarness:
    """Manager-owned gateway process: one fence, receipt table and device state."""

    def __init__(self):
        self.adapter = ControlledVirtualAdapter()
        self.gateway = AdapterDeviceGateway(self.adapter)

    def block_first_write(self):
        self.adapter.entered.clear()
        self.adapter.release.clear()
        self.adapter.block_next = True

    def wait_write_started(self, timeout=15):
        return self.adapter.entered.wait(timeout)

    def release_write(self):
        self.adapter.release.set()

    def list_capabilities(self):
        return self.adapter.list_capabilities()

    def read_state(self):
        return self.adapter.read_state()

    def read_value(self, device):
        return self.adapter.read_value(device)

    def write(self, device, command, value):
        return self.adapter.write(device, command, value)

    def reset(self):
        return self.adapter.reset()

    def list_devices(self, space_id):
        return self.gateway.list_devices(space_id)

    def advance_fence(self, space_id, epoch):
        return self.gateway.advance_fence(space_id, epoch)

    def submit(self, request):
        return self.gateway.submit(request)

    def query(self, action_id):
        return self.gateway.query(action_id)


class HarnessManager(BaseManager):
    pass


HarnessManager.register("harness", SharedHarness)


class ProxyAdapter:
    def __init__(self, shared):
        self.space_id = SPACE
        self.shared = shared

    def list_capabilities(self):
        return self.shared.list_capabilities()

    def read_state(self):
        return self.shared.read_state()

    def read_value(self, device):
        return self.shared.read_value(device)

    def write(self, device, command, value):
        return self.shared.write(device, command, value)

    def reset(self):
        return self.shared.reset()


class ProxyGateway:
    def __init__(self, adapter, shared):
        self.adapter = adapter  # RestService's identity check must keep this gateway
        self.shared = shared

    def list_devices(self, space_id):
        return self.shared.list_devices(space_id)

    def advance_fence(self, space_id, epoch):
        return self.shared.advance_fence(space_id, epoch)

    def submit(self, request):
        return self.shared.submit(request)

    def query(self, action_id):
        return self.shared.query(action_id)


def _service(shared):
    svc = RestService(store=SqlStore(), preferences=SqlPreferenceRepository())
    adapter = ProxyAdapter(shared)
    svc._devices[SPACE] = adapter
    svc._gateways[SPACE] = ProxyGateway(adapter, shared)
    return svc


def _confirm_worker(shared, database_url, redis_url, plan_id, version, start, result, ready=None, ttl_s=None):
    # Spawned process: settings modules may already have been imported by test discovery.
    from app import config
    from app.cache import reset_client
    from app.db.session import reset_engine

    config.DATABASE_URL = database_url
    config.REDIS_URL = redis_url
    reset_engine()
    reset_client()
    svc = _service(shared)
    if ttl_s is not None:
        from app.cache import SpaceLock

        svc._space_lock = lambda space_id: SpaceLock(space_id, ttl_s=ttl_s)
    if ready is not None:
        ready.put(os.getpid())
    assert start.wait(30)
    context = RequestContext(account_id="demo-account", person_id="person-lin", space_id=SPACE)
    try:
        response = svc.confirm_plan(plan_id, context, version)
        result.put(("ok", response.service.service_id if response.service else None))
    except Exception as exc:
        result.put(("error", getattr(exc, "code", type(exc).__name__)))


def test_two_processes_confirm_one_plan_through_one_gateway(sql_store):
    database_url = os.environ["LIVINGMIND_TEST_DATABASE_URL"]
    redis_url = os.environ.get("LIVINGMIND_TEST_REDIS_URL", "")
    context = mp.get_context("spawn")
    manager = HarnessManager(ctx=context)
    manager.start()
    try:
        shared = manager.harness()
        parent = _service(shared)
        rc = RequestContext(account_id="demo-account", person_id="person-lin", space_id=SPACE)
        plan = parent.create_rest_plan(rc, "我想休息")
        start = context.Event()
        result = context.Queue()
        ready = context.Queue()
        workers = [context.Process(target=_confirm_worker, args=(shared, database_url, redis_url,
                     plan.plan_id, plan.version, start, result, ready)) for _ in range(2)]
        for worker in workers:
            worker.start()
        # Both API processes finish startup recovery before either accepts traffic.
        for _ in workers:
            ready.get(timeout=30)
        start.set()
        outcomes = [result.get(timeout=25) for _ in workers]
        for worker in workers:
            worker.join(timeout=5)
            assert worker.exitcode == 0
        assert sum(kind == "ok" for kind, _ in outcomes) >= 1, outcomes
        assert shared.read_state().version == 3, "each of the three device writes must happen once"
        assert parent._store.active_service(SPACE) is not None
    finally:
        manager.shutdown()


class RedisFaultProxy(socketserver.ThreadingTCPServer):
    """Test-only TCP forwarding; cutting it closes established and new connections."""

    daemon_threads = True

    def __init__(self, redis_url):
        parsed = urlsplit(redis_url)
        assert parsed.scheme == "redis", "the disposable fault proxy uses plain test Redis"
        self.upstream = (parsed.hostname, parsed.port or 6379)
        self.cut = Event()
        super().__init__(("127.0.0.1", 0), RedisProxyHandler)
        credentials = parsed.netloc.rsplit("@", 1)[0] + "@" if "@" in parsed.netloc else ""
        self.url = urlunsplit(parsed._replace(netloc=f"{credentials}127.0.0.1:{self.server_address[1]}"))
        self.thread = Thread(target=self.serve_forever, daemon=True)
        self.thread.start()

    def close(self):
        self.cut.set()
        self.shutdown()
        self.server_close()
        self.thread.join(timeout=2)


class RedisProxyHandler(socketserver.BaseRequestHandler):
    def handle(self):
        if self.server.cut.is_set():
            return
        try:
            with socket.create_connection(self.server.upstream, timeout=1) as upstream:
                peers = {self.request: upstream, upstream: self.request}
                while not self.server.cut.is_set():
                    readable, _, _ = select.select(list(peers), [], [], 0.05)
                    for source in readable:
                        data = source.recv(65536)
                        if not data:
                            return
                        peers[source].sendall(data)
        except OSError:
            pass  # the injected transport cut is the purpose of this test server


@needs_redis
@pytest.mark.parametrize("fault", ["lease_expired", "redis_disconnected"])
def test_duplicate_confirmation_during_a_slow_write_survives_coordination_loss(sql_store, fault):
    """Real processes and TCP: SQL's recorded plan survives Redis TTL or link loss."""
    import redis
    from app.cache.keys import space_executor_lock

    database_url = os.environ["LIVINGMIND_TEST_DATABASE_URL"]
    redis_url = os.environ["LIVINGMIND_TEST_REDIS_URL"]
    context = mp.get_context("spawn")
    manager = HarnessManager(ctx=context)
    manager.start()
    proxy = RedisFaultProxy(redis_url)
    probe = redis.Redis.from_url(redis_url)
    workers = []
    try:
        shared = manager.harness()
        parent = _service(shared)
        rc = RequestContext(account_id="demo-account", person_id="person-lin", space_id=SPACE)
        plan = parent.create_rest_plan(rc, "我想休息")
        starts = [context.Event(), context.Event()]
        ready = context.Queue()
        results = [context.Queue(), context.Queue()]
        for index in range(2):
            worker = context.Process(target=_confirm_worker, args=(
                shared, database_url, proxy.url, plan.plan_id, plan.version,
                starts[index], results[index], ready, 1 if fault == "lease_expired" else 30,
            ))
            workers.append(worker)
            worker.start()
        for _ in workers:
            ready.get(timeout=30)
        shared.block_first_write()
        starts[0].set()
        assert shared.wait_write_started(15)
        if fault == "lease_expired":
            deadline = time.monotonic() + 5
            while probe.exists(space_executor_lock(SPACE)) and time.monotonic() < deadline:
                time.sleep(0.05)
            assert not probe.exists(space_executor_lock(SPACE))
        else:
            assert probe.exists(space_executor_lock(SPACE)), "the first worker really acquired Redis"
            proxy.cut.set()
        starts[1].set()
        assert results[1].get(timeout=15)[0] == "ok"
        assert shared.read_state().version == 0, "the duplicate must not write while the original is blocked"
        shared.release_write()
        assert results[0].get(timeout=20)[0] == "ok"
        for worker in workers:
            worker.join(timeout=5)
            assert worker.exitcode == 0
        assert shared.read_state().version == 3
    finally:
        for worker in workers:
            if worker.is_alive():
                worker.terminate()
                worker.join(timeout=5)
        probe.close()
        proxy.close()
        manager.shutdown()


def test_stop_from_other_process_blocks_remaining_actions_and_fences_late_command(sql_store):
    database_url = os.environ["LIVINGMIND_TEST_DATABASE_URL"]
    redis_url = os.environ.get("LIVINGMIND_TEST_REDIS_URL", "")
    context = mp.get_context("spawn")
    manager = HarnessManager(ctx=context)
    manager.start()
    try:
        shared = manager.harness()
        parent = _service(shared)
        rc = RequestContext(account_id="demo-account", person_id="person-lin", space_id=SPACE)
        plan = parent.create_rest_plan(rc, "我想休息")
        initial_epoch = parent._store.epoch(SPACE)
        shared.block_first_write()
        start, result = context.Event(), context.Queue()
        worker = context.Process(target=_confirm_worker, args=(shared, database_url, redis_url,
                                  plan.plan_id, plan.version, start, result))
        worker.start()
        start.set()
        assert shared.wait_write_started(15)
        try:
            active = parent._store.active_service(SPACE)
            assert active is not None
            stopped = parent.stop_service(active.service_id, rc)
            assert stopped.service.status == "stopped"
        finally:
            shared.release_write()
        assert result.get(timeout=25)[0] == "ok"
        worker.join(timeout=5)
        assert worker.exitcode == 0
        # The command already in flight may complete; the other two must not start.
        assert shared.read_state().version == 1
        stale = shared.submit(DeviceCommandRequest(
            action_id="late-after-stop", service_id=active.service_id, service_epoch=initial_epoch,
            device_id=f"{SPACE}:light", device_type="light", command="set_brightness", value=99,
            requested_at=utc_now(),
        ))
        assert stale.status == "rejected"
        assert shared.read_state().version == 1
    finally:
        manager.shutdown()


def test_crashed_api_marks_uncertain_action_unknown_without_replaying_gateway_write(sql_store):
    from app.api.errors import ApiError
    from app.cache.keys import space_executor_lock

    database_url = os.environ["LIVINGMIND_TEST_DATABASE_URL"]
    redis_url = os.environ.get("LIVINGMIND_TEST_REDIS_URL", "")
    context = mp.get_context("spawn")
    manager = HarnessManager(ctx=context)
    manager.start()
    worker = None
    try:
        shared = manager.harness()
        parent = _service(shared)
        rc = RequestContext(account_id="demo-account", person_id="person-lin", space_id=SPACE)
        plan = parent.create_rest_plan(rc, "我想休息")
        shared.block_first_write()
        start, result = context.Event(), context.Queue()
        worker = context.Process(target=_confirm_worker, args=(shared, database_url, redis_url,
                                  plan.plan_id, plan.version, start, result, None, 3))
        worker.start()
        start.set()
        assert shared.wait_write_started(15)
        worker.terminate()  # kill only this disposable test API process, not the gateway
        worker.join(timeout=10)
        assert worker.exitcode is not None and worker.exitcode != 0
        shared.release_write()
        for _ in range(50):
            receipt = shared.query(plan.actions[0].action_id)
            if receipt is not None and receipt.status == "completed":
                break
            time.sleep(0.1)
        assert receipt.status == "completed"
        assert shared.read_state().version == 1

        restarted = _service(shared)
        assert restarted._recovery.unknown_actions == 1
        assert restarted._store.get_action_execution(plan.actions[0].action_id).status == "unknown"
        if redis_url:
            import redis

            with redis.Redis.from_url(redis_url) as probe:
                # The dead process cannot release its token. An immediate retry may
                # correctly be busy; only TTL expiry permits another lock holder.
                if probe.pttl(space_executor_lock(SPACE)) > 500:
                    with pytest.raises(ApiError) as busy:
                        restarted.confirm_plan(plan.plan_id, rc, plan.version)
                    assert busy.value.code == "SPACE_BUSY"
                deadline = time.monotonic() + 5
                while probe.exists(space_executor_lock(SPACE)) and time.monotonic() < deadline:
                    time.sleep(0.05)
                assert not probe.exists(space_executor_lock(SPACE))
        # Repeating confirmation reads the old service, never sends action 1/2/3 again.
        restarted.confirm_plan(plan.plan_id, rc, plan.version)
        assert shared.read_state().version == 1
    finally:
        if worker is not None and worker.is_alive():
            worker.terminate()
            worker.join(timeout=5)
        manager.shutdown()

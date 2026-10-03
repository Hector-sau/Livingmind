"""Two real API HTTP processes, one durable HTTP virtual gateway, shared SQL.

The proxy injects response loss/delay after the gateway commits. No vendor device,
production traffic or model API is involved. Redis is deliberately disabled here:
the database lock must serialize writes independently of the optional cache.
"""
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
import time

import httpx
import pytest
from tests.conftest import TEST_DB_URL, TEST_REDIS_URL, ctx
from tests.test_cache_coordination import needs_redis
from tests.test_persistence import needs_db
from tests.test_persistent_gateway import Server, SPACE, TOKEN, gateway_process

pytestmark = needs_db
BOOT = "/api/bootstrap?accountId=demo-account"


class Proxy(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, target):
        super().__init__(("127.0.0.1", 0), Handler)
        self.target = target
        self.block_next = False
        self.lose_next = False
        self.entered, self.release = threading.Event(), threading.Event()
        self.thread = threading.Thread(target=self.serve_forever, daemon=True)
        self.thread.start()

    def close(self):
        self.release.set()
        self.shutdown()
        self.server_close()
        self.thread.join(5)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def forward(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else None
        response = httpx.request(self.command, self.server.target + self.path, content=body,
                                 headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}, timeout=5)
        if self.path == "/commands":
            if self.server.block_next:
                self.server.block_next = False
                self.server.entered.set()
                self.server.release.wait(15)
            if self.server.lose_next:
                self.server.lose_next = False
                self.close_connection = True
                return
        try:
            self.send_response(response.status_code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(response.content)))
            self.end_headers()
            self.wfile.write(response.content)
        except (BrokenPipeError, ConnectionResetError):
            pass

    do_GET = do_POST = forward


@pytest.fixture
def replicas(sql_store, gateway_process, request):
    proxy = Proxy(gateway_process.url)
    proxy.redis_link = None
    if getattr(request, "param", None) == "redis":
        from tests.test_multiprocess_gateway import RedisFaultProxy
        proxy.redis_link = RedisFaultProxy(TEST_REDIS_URL)
    env = {"LIVINGMIND_DATABASE_URL": TEST_DB_URL, "LIVINGMIND_REDIS_URL": proxy.redis_link.url if proxy.redis_link else "",
           "LIVINGMIND_GATEWAY_URL": f"http://127.0.0.1:{proxy.server_port}",
           "LIVINGMIND_GATEWAY_TOKEN": TOKEN, "LIVINGMIND_GATEWAY_TIMEOUT_S": "12",
           "LIVINGMIND_ORCHESTRATOR": "legacy", "LIVINGMIND_PLANNER_MODE": "rule",
           "LIVINGMIND_DEMO_LOCAL_HOUR": "20", "LIVINGMIND_DB_DISABLE_POOL": "1"}
    servers = [Server("app.main:app", env), Server("app.main:app", env)]
    try:
        servers[0].start(BOOT)
        yield servers, proxy, gateway_process
    finally:
        proxy.release.set()
        for server in servers:
            server.stop()
        proxy.close()
        if proxy.redis_link:
            proxy.redis_link.close()


def post(server, path, body):
    return httpx.post(server.url + path, json=body, timeout=20)


def plan(server):
    response = post(server, "/api/plans/rest", {"context": ctx(), "utterance": "我想休息", "mode": "rule"})
    assert response.status_code == 200, response.text
    return response.json()


def confirm(server, item):
    return post(server, f"/api/plans/{item['planId']}/confirm", {"context": ctx(), "planVersion": item["version"]})


def state(server):
    return httpx.get(server.url + BOOT, timeout=10).json()["deviceState"]


def test_two_http_apis_share_state_and_undo(replicas):
    (a, b), _, _ = replicas
    b.start(BOOT)
    result = post(a, f"/api/spaces/{SPACE}/devices/control", {"context": ctx(), "device": "light", "value": 30})
    assert result.status_code == 200, result.text
    assert state(b)["lightBrightness"] == 30
    undo = post(b, f"/api/devices/undo/{result.json()['undo']['undoId']}", {"context": ctx()})
    assert undo.status_code == 200, undo.text
    assert state(a)["lightBrightness"] == seed_light()
    assert state(a)["version"] == 2


def test_fresh_gateway_reset_and_shared_energy_reset(replicas):
    (a, b), _, _ = replicas
    b.start(BOOT)
    first = post(b, "/api/demo/reset?accountId=demo-account", {})
    assert first.status_code == 200, first.text
    assert state(a)["version"] == 1
    changed = httpx.put(a.url + f"/api/spaces/{SPACE}/energy-mode", json={"context": ctx(), "mode": "eco"}, timeout=10)
    assert changed.status_code == 200, changed.text
    assert httpx.get(b.url + BOOT).json()["spaces"][0]["energyMode"] == "eco"
    reset = post(b, "/api/demo/reset?accountId=demo-account", {})
    assert reset.status_code == 200, reset.text
    assert httpx.get(a.url + BOOT).json()["spaces"][0]["energyMode"] == "comfort_first"
    assert state(a)["version"] == 2


def seed_light():
    from app.demo import seed
    return seed.INITIAL_DEVICE_STATE["light_brightness"]


def test_live_owner_is_not_cancelled_and_other_api_can_stop(replicas, sql_store):
    (a, b), proxy, _ = replicas
    item = plan(a)
    proxy.block_next = True
    with ThreadPoolExecutor() as pool:
        pending = pool.submit(confirm, a, item)
        assert proxy.entered.wait(10)
        # Starting B while A is dispatching must NOT turn A's action into unknown.
        b.start(BOOT)
        execution = sql_store.get_action_execution(item["actions"][0]["actionId"])
        assert execution.status == "dispatching"
        service = sql_store.active_service(SPACE)
        stop = post(b, f"/api/services/{service.service_id}/stop", {"context": ctx()})
        assert stop.status_code == 200, stop.text
        proxy.release.set()
        result = pending.result(15)
    assert result.status_code == 200, result.text
    assert result.json()["service"]["status"] == "stopped"
    assert [x["outcome"] for x in result.json()["results"]] == ["succeeded", "skipped", "skipped"]
    assert state(b)["version"] == 1


def test_two_http_confirmations_and_different_plan_competition(replicas):
    (a, b), proxy, _ = replicas
    b.start(BOOT)
    item, other = plan(a), plan(b)
    proxy.block_next = True
    with ThreadPoolExecutor() as pool:
        pending = pool.submit(confirm, a, item)
        assert proxy.entered.wait(10)
        duplicate = confirm(b, item)
        conflict = confirm(b, other)
        assert duplicate.status_code == conflict.status_code == 409
        assert conflict.json()["error"]["code"] == "SPACE_BUSY"
        reset = post(b, "/api/demo/reset?accountId=demo-account", {})
        assert reset.status_code == 409  # no concurrent destructive demo reset
        proxy.release.set()
        assert pending.result(15).status_code == 200
    assert confirm(b, item).json()["repeated"] is True
    assert confirm(b, other).json()["error"]["code"] == "SERVICE_ALREADY_ACTIVE"
    assert state(b)["version"] == 3


def test_lost_reply_is_reconciled_after_gateway_restart(replicas):
    (a, b), proxy, gateway = replicas
    b.start(BOOT)
    item = plan(a)
    proxy.lose_next = True
    response = confirm(a, item)
    assert response.status_code == 200, response.text
    assert response.json()["results"][0]["outcome"] == "unknown"
    gateway.stop(kill=True)
    gateway.start(headers={"Authorization": f"Bearer {TOKEN}"})
    action_id = item["actions"][0]["actionId"]
    result = post(b, f"/api/actions/{action_id}/reconcile", {"context": ctx()})
    assert result.status_code == 200 and result.json()["status"] == "completed"
    assert confirm(b, item).json()["results"][0]["outcome"] == "succeeded"
    assert state(b)["version"] == 3


def test_api_crash_recovers_only_dead_owner_without_replaying(replicas, sql_store):
    (a, b), proxy, _ = replicas
    item = plan(a)
    proxy.block_next = True
    with ThreadPoolExecutor() as pool:
        pending = pool.submit(confirm, a, item)
        assert proxy.entered.wait(10)
        a.stop(kill=True)
        proxy.release.set()
        with pytest.raises(httpx.HTTPError):
            pending.result(10)
    b.start(BOOT)
    action_id = item["actions"][0]["actionId"]
    assert sql_store.get_action_execution(action_id).status == "unknown"
    response = post(b, f"/api/actions/{action_id}/reconcile", {"context": ctx()})
    assert response.json()["status"] == "completed"
    repeated = confirm(b, item).json()
    assert repeated["repeated"] is True
    assert len(repeated["results"]) == 1 and repeated["results"][0]["outcome"] == "succeeded"
    assert state(b)["version"] == 1


def test_stop_survives_gateway_outage_without_claiming_device_state(replicas, sql_store):
    (a, b), _, gateway = replicas
    b.start(BOOT)
    started = confirm(a, plan(a)).json()
    service_id = started["service"]["serviceId"]
    gateway.stop(kill=True)
    stopped = post(b, f"/api/services/{service_id}/stop", {"context": ctx()})
    assert stopped.status_code == 200, stopped.text
    assert stopped.json()["service"]["status"] == "stopped"
    assert stopped.json()["deviceState"] is None
    assert "在途动作" in stopped.json()["warning"]
    assert sql_store.get_service(service_id).status == "stopped"
    gateway.start(headers={"Authorization": f"Bearer {TOKEN}"})
    assert state(a)["version"] == 3  # the stop never restores or repeats commands


@needs_redis
@pytest.mark.parametrize("replicas,fault", [("redis", "ttl"), ("redis", "disconnect")], indirect=["replicas"])
def test_http_replicas_keep_exclusive_execution_after_redis_coordination_loss(replicas, fault):
    import redis
    from app.cache.keys import space_executor_lock

    (a, b), proxy, _ = replicas
    b.start(BOOT)
    first, different = plan(a), plan(b)
    proxy.block_next = True
    with redis.Redis.from_url(TEST_REDIS_URL) as probe, ThreadPoolExecutor() as pool:
        pending = pool.submit(confirm, a, first)
        assert proxy.entered.wait(10)
        key = space_executor_lock(SPACE)
        assert probe.exists(key), "the API really acquired the Redis lease"
        if fault == "ttl":
            probe.pexpire(key, 50)  # accelerate this test lease, not the production TTL
            deadline = time.monotonic() + 2
            while probe.exists(key) and time.monotonic() < deadline:
                time.sleep(.02)
            assert not probe.exists(key)
        else:
            proxy.redis_link.cut.set()  # cut established and future TCP connections
        blocked = confirm(b, different)
        assert blocked.status_code == 409 and blocked.json()["error"]["code"] == "SPACE_BUSY"
        blocked_control = post(b, f"/api/spaces/{SPACE}/devices/control", {"context": ctx(), "device": "light", "value": 60})
        assert blocked_control.status_code == 409
        assert state(b)["version"] == 1
        proxy.release.set()
        assert pending.result(15).status_code == 200
        assert state(b)["version"] == 3
    if fault == "disconnect":
        # Once SQL execution ownership is released, unavailable Redis does not
        # stop a subsequent explicit device control from going through the guard.
        result = post(b, f"/api/spaces/{SPACE}/devices/control", {"context": ctx(), "device": "light", "value": 60})
        assert result.status_code == 200, result.text
        assert state(b)["version"] == 4

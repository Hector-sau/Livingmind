"""Real gateway HTTP process + durable virtual state, never physical-device evidence."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

import httpx
import pytest
from fastapi.testclient import TestClient

from app.adapters.gateway_app import create_app
from app.adapters.http_gateway import HttpDeviceAdapter, HttpDeviceGateway
from app.adapters.persistent_gateway import PersistentVirtualGateway
from app.adapters.protocol import DeviceCommandRequest
from app.clock import utc_now
from app.demo import seed

SPACE = "space-home-bedroom"
TOKEN = "test-only-local-gateway-token"


def command(action_id="a1", epoch=0, value=20):
    return DeviceCommandRequest(action_id, None, epoch, f"{SPACE}:light", "light", "set_brightness", value, utc_now())


def test_state_receipt_and_fence_survive_reopening(tmp_path):
    path = str(tmp_path / "gateway.sqlite3")
    make = lambda: PersistentVirtualGateway(path, {SPACE: seed.INITIAL_DEVICE_STATE})
    first = make().submit(command())
    second = make()
    assert second.query("a1") == first == second.submit(command())
    assert second.state(SPACE).version == 1
    assert second.submit(command(value=30)).status == "rejected"
    second.fence(SPACE, 3)
    assert make().submit(command("old", 2)).status == "rejected"
    assert make().state(SPACE).version == 1


def test_concurrent_duplicate_writes_commit_once(tmp_path):
    gateway = PersistentVirtualGateway(str(tmp_path / "state.db"), {SPACE: seed.INITIAL_DEVICE_STATE})
    with ThreadPoolExecutor(max_workers=8) as pool:
        receipts = list(pool.map(lambda _: gateway.submit(command()), range(16)))
    assert all(r == receipts[0] for r in receipts)
    assert gateway.state(SPACE).version == 1


def test_reset_keeps_receipts_and_rejects_stale_reset(tmp_path):
    gateway = PersistentVirtualGateway(str(tmp_path / "state.db"), {SPACE: seed.INITIAL_DEVICE_STATE})
    receipt = gateway.submit(command())
    assert gateway.reset(SPACE, 1)
    assert gateway.query("a1") == receipt
    version = gateway.state(SPACE).version
    assert not gateway.reset(SPACE, 1)
    assert gateway.submit(command("late", 0)).status == "rejected"
    assert gateway.state(SPACE).version == version


@pytest.mark.parametrize("change", [{"device_id": "unknown:light"}, {"device_type": "ac"},
                                    {"value": 101}, {"value": 2.5}, {"service_epoch": -1}])
def test_gateway_revalidates_command_identity_and_bounds(tmp_path, change):
    gateway = PersistentVirtualGateway(str(tmp_path / "state.db"), {SPACE: seed.INITIAL_DEVICE_STATE})
    assert gateway.submit(replace(command(), **change)).status == "rejected"
    assert gateway.state(SPACE).version == 0


def test_internal_gateway_requires_token(tmp_path):
    client = TestClient(create_app(str(tmp_path / "state.db"), TOKEN))
    assert client.get(f"/spaces/{SPACE}/state").status_code == 401
    assert client.get(f"/spaces/{SPACE}/state", headers={"Authorization": f"Bearer {TOKEN}"}).status_code == 200


def port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class Server:
    def __init__(self, module, env, *, factory=False):
        self.port = port()
        self.url = f"http://127.0.0.1:{self.port}"
        self.args = [sys.executable, "-m", "uvicorn", module, "--host", "127.0.0.1", "--port", str(self.port)]
        if factory:
            self.args.append("--factory")
        self.env = {**os.environ, **env, "PYTHONDONTWRITEBYTECODE": "1"}
        self.process = None

    def start(self, path="/health", headers=None):
        self.process = subprocess.Popen(self.args, env=self.env, cwd=Path(__file__).resolve().parents[1],
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                raise RuntimeError("test server exited before readiness")
            try:
                if httpx.get(self.url + path, headers=headers, timeout=.5).status_code == 200:
                    return self
            except httpx.HTTPError:
                pass
            time.sleep(.05)
        self.stop()
        raise RuntimeError("test server did not become ready")

    def stop(self, kill=False):
        if self.process is not None and self.process.poll() is None:
            self.process.kill() if kill else self.process.terminate()
            self.process.wait(10)


@pytest.fixture
def gateway_process(tmp_path):
    server = Server("app.adapters.gateway_app:create_app", {
        "LIVINGMIND_GATEWAY_DATA": str(tmp_path / "gateway.db"), "LIVINGMIND_GATEWAY_TOKEN": TOKEN,
    }, factory=True)
    server.start(headers={"Authorization": f"Bearer {TOKEN}"})
    try:
        yield server
    finally:
        server.stop()


def test_gateway_process_restart_retains_receipt(gateway_process):
    adapter = HttpDeviceAdapter(SPACE, gateway_process.url, TOKEN, lambda _: 0)
    gateway = HttpDeviceGateway(adapter)
    try:
        original = gateway.submit(command())
        gateway_process.stop(kill=True)
        gateway_process.start(headers={"Authorization": f"Bearer {TOKEN}"})
        assert gateway.query("a1") == original
        assert gateway.submit(command()) == original
        assert adapter.read_state().version == 1
        with pytest.raises(RuntimeError, match="actionId"):
            adapter.write("light", "set_brightness", 30)
    finally:
        adapter.close()

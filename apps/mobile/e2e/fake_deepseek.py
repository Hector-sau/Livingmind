"""Local stand-in for the DeepSeek chat endpoint. E2E ONLY — results from it are NOT real model calls.

Behaviour is chosen by words in the user message:
  "慢"   -> sleeps longer than the backend timeout (tests timeout fallback)
  "很亮" -> proposes 100% light (tests the deviation limit fallback)
  other  -> a valid plan (light 10, AC 24, curtain 0)
"""

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

VALID = {
    "goal": "安静昏暗、略凉的休息环境",
    "rationale": "用户说有点热，比偏好低 1 度",
    "light_brightness": 10,
    "ac_target_temp_c": 24,
    "curtain_open_percent": 0,
    "needs_clarification": False,
    "clarification_question": None,
}

_hold_adjustment = threading.Event()
_adjustment_started = threading.Event()
_release_adjustment = threading.Event()


def hold_next_adjustment() -> None:
    """Test control: pause one adjustment model call until the scenario releases it."""
    _adjustment_started.clear()
    _release_adjustment.clear()
    _hold_adjustment.set()


def wait_for_adjustment(timeout: float = 3) -> bool:
    return _adjustment_started.wait(timeout)


def release_adjustment() -> None:
    _release_adjustment.set()


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
        if not self.headers.get("Authorization", "").startswith("Bearer "):
            self.send_response(401)
            self.end_headers()
            return
        user = body["messages"][1]["content"]
        reply = dict(VALID)
        if _hold_adjustment.is_set() and "【模拟环境事件】" in user:
            _hold_adjustment.clear()
            _adjustment_started.set()
            _release_adjustment.wait(timeout=5)
        if "慢" in user:
            time.sleep(8)
        if "很亮" in user:
            reply["light_brightness"] = 100
        out = json.dumps({"choices": [{"message": {"content": json.dumps(reply, ensure_ascii=False)}}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *args):
        pass


def serve(port: int, host: str = "127.0.0.1") -> ThreadingHTTPServer:
    """Create the stub server; loopback remains the safe local default.

    Linux Docker containers reach a host-side test stub through the bridge
    gateway, so CI explicitly passes ``0.0.0.0`` while the server is running.
    """
    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True
    return server

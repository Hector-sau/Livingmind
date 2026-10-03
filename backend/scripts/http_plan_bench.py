"""Paired, isolated HTTP planning benchmark. No credentials or paid calls.

Runs loopback API -> real provider HTTP code -> local model stub. It measures client
connection reuse, NOT DeepSeek inference, TLS over the internet or tablet latency.
Fresh/pooled order alternates by repetition; every row retains its request ID,
latency, stage times and result. Nothing touches a configured demo database.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
from pathlib import Path
import re
import socket
import sys
import threading
import time
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
import uvicorn

from app import config
from app.agents.experience.provider import DeepSeekProvider
from app.clock import utc_now
from app.demo import seed
from app.main import create_app
from app.memory.repository import InMemoryPreferenceRepository
from app.repositories.store import MemoryStore
from app.services.planner import Planner
from app.services.rest_service import RestService, get_rest_service


def quantile(values: list[float], fraction: float) -> float | None:
    import math
    return sorted(values)[max(0, math.ceil(len(values) * fraction) - 1)] if values else None


def summarize(rows: list[dict]) -> dict:
    latencies = [row["elapsed_ms"] for row in rows]  # include errors; no fast-success filtering
    return {"requests": len(rows), "valid_plans": sum(row["valid"] for row in rows),
            "errors": sum(row["error"] is not None for row in rows),
            "p50_ms": quantile(latencies, .5), "p95_ms": quantile(latencies, .95)}


class ModelStub(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self):
        super().__init__(("127.0.0.1", 0), ModelHandler)
        self.connections = 0

    def get_request(self):
        result = super().get_request()
        result[0].setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.connections += 1
        return result


class ModelHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *_):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        prompt = body["messages"][-1]["content"]
        match = re.search(r"灯光 ([\d.]+)%，空调 ([\d.]+)°C，窗帘开度 ([\d.]+)%", prompt)
        if not match:
            self.send_error(400)
            return
        light, ac, curtain = map(float, match.groups())
        content = json.dumps({"goal": "模拟休息方案", "rationale": "按当前人物偏好",
                              "light_brightness": int(light), "ac_target_temp_c": ac,
                              "curtain_open_percent": int(curtain), "needs_clarification": False,
                              "clarification_question": None}, ensure_ascii=False)
        payload = json.dumps({"choices": [{"finish_reason": "stop", "message": {"content": content}}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)
        self.wfile.flush()


@contextmanager
def serve(app):
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, log_level="error", access_log=False))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 10
        while not server.started:
            if not thread.is_alive() or time.monotonic() > deadline:
                raise RuntimeError("isolated API failed to start")
            time.sleep(.01)
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(10)
        sock.close()
        if thread.is_alive():
            raise RuntimeError("isolated API did not stop cleanly")


def run_variant(stub: ModelStub, pooled: bool, rounds: int, concurrency: int) -> dict:
    captured = []

    class Capture(logging.Handler):
        def emit(self, record):
            captured.append(json.loads(record.getMessage()))

    handler = Capture()
    logger = logging.getLogger("livingmind.events")
    logger.addHandler(handler)
    provider = DeepSeekProvider("local-stub-not-a-key", "local-stub", f"http://127.0.0.1:{stub.server_port}",
                                reuse_connections=pooled)
    service = RestService(planner=Planner("model", provider, 6, utc_now),
                          store=MemoryStore(), preferences=InMemoryPreferenceRepository())
    app = create_app()
    app.dependency_overrides[get_rest_service] = lambda: service
    try:
        with serve(app) as url, httpx.Client(base_url=url, timeout=15) as client:
            def request(index):
                person = seed.PERSONS[index % len(seed.PERSONS)]
                request_id = uuid.uuid4().hex
                started = time.perf_counter()
                error, valid, status = None, False, None
                try:
                    response = client.post("/api/assistant/messages", headers={"X-Request-ID": request_id}, json={
                        "context": {"accountId": "demo-account", "personId": person.person_id,
                                    "spaceId": seed.DEFAULT_SPACE_ID},
                        "text": "我想休息，按平时的偏好", "mode": "model", "conversationId": request_id,
                    })
                    status = response.status_code
                    plan = response.json().get("plan")
                    expected = person.rest_preference
                    valid = status == 200 and plan is not None and plan["source"] == "model" and {
                        action["device"]: action["value"] for action in plan["actions"]
                    } == {"light": expected.light_brightness, "ac": expected.ac_target_temp_c,
                          "curtain": expected.curtain_open_percent}
                    if not valid:
                        error = "unexpected_plan_or_status"
                except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
                    error = type(exc).__name__
                return {"request_id": request_id, "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
                        "status": status, "valid": bool(valid), "error": error}

            # Same warm-up in each variant; recorded separately from measured requests.
            warmup = [request(i) for i in range(2)]
            if not all(row["valid"] for row in warmup):
                raise RuntimeError("benchmark warm-up did not produce valid plans")
            connections_before = stub.connections
            start = time.perf_counter()
            with ThreadPoolExecutor(max_workers=concurrency) as pool:
                rows = list(pool.map(request, range(rounds)))
            duration = time.perf_counter() - start
            connection_count = stub.connections - connections_before
        for row in rows:
            row["stages"] = {item["agent"]: item["durationMs"] for item in captured
                             if item.get("requestId") == row["request_id"] and item.get("event") == "agent.stage"}
        return {"variant": "pooled" if pooled else "fresh", "concurrency": concurrency,
                "warmup_requests": 2, "new_model_connections": connection_count,
                "wall_seconds": round(duration, 3), "summary": summarize(rows), "rows": rows}
    finally:
        provider.close()
        logger.removeHandler(handler)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rounds", type=int, default=20)
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--concurrency", type=int, nargs="+", default=[1, 5])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not 1 <= args.rounds <= 1000 or not 1 <= args.repeats <= 10 or any(not 1 <= c <= 20 for c in args.concurrency):
        parser.error("rounds 1..1000; repeats 1..10; concurrency 1..20")
    # Deliberately isolated regardless of inherited environment variables.
    config.DATABASE_URL, config.REDIS_URL, config.ORCHESTRATOR = "", "", "legacy"
    for name in ("livingmind.http", "livingmind.events"):
        for handler in logging.getLogger(name).handlers:
            handler.setLevel(logging.CRITICAL)
    stub = ModelStub()
    thread = threading.Thread(target=stub.serve_forever, daemon=True)
    thread.start()
    try:
        runs = []
        for concurrency in args.concurrency:
            for repeat in range(args.repeats):
                for pooled in ([False, True] if repeat % 2 == 0 else [True, False]):
                    run = run_variant(stub, pooled, args.rounds, concurrency)
                    run["repeat"] = repeat
                    runs.append(run)
                    print(json.dumps({k: v for k, v in run.items() if k != "rows"}), flush=True)
        result = {"recorded_at_utc": datetime.now(timezone.utc).isoformat(),
                  "scope": "loopback HTTP API + local model stub; memory store; legacy; no TLS; no real inference",
                  "synthetic": True, "paid_calls": 0, "order": "alternated per repetition", "runs": runs}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return 0 if all(run["summary"]["errors"] == 0 for run in runs) else 1
    finally:
        stub.shutdown()
        stub.server_close()
        thread.join(5)


if __name__ == "__main__":
    raise SystemExit(main())

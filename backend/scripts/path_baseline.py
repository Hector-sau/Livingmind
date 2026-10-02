"""Measure a complete local rule-mode HTTP path, excluding model/network/hardware time.

    cd backend
    python scripts/path_baseline.py --rounds 30 --output /private/tmp/livingmind-path.json

This is a reproducible in-process TestClient baseline, not tablet or production latency.
The plan's agent trace provides stage-level timings; the confirm phase includes virtual
gateway receipts and readback. Requests are correlated through X-Request-ID.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import create_app  # noqa: E402
from app.memory.repository import InMemoryPreferenceRepository  # noqa: E402
from app.repositories.store import MemoryStore  # noqa: E402
from app.services.rest_service import RestService, get_rest_service  # noqa: E402
from scripts.evaluate_holdout import percentile  # noqa: E402

CONTEXT = {"accountId": "demo-account", "personId": "person-lin", "spaceId": "space-home-bedroom"}


def run(rounds: int) -> dict:
    service = RestService(store=MemoryStore(), preferences=InMemoryPreferenceRepository())
    app = create_app()
    app.dependency_overrides[get_rest_service] = lambda: service
    rows = []
    with TestClient(app) as client:
        for number in range(rounds):
            request_id = f"baseline-{number + 1}"
            started = time.monotonic()
            response = client.post("/api/assistant/messages", json={"context": CONTEXT, "text": "我想休息", "mode": "rule"},
                                   headers={"X-Request-ID": request_id})
            plan_ms = int((time.monotonic() - started) * 1000)
            assert response.status_code == 200, response.text
            plan = response.json()["plan"]
            assert plan is not None and response.headers["X-Request-ID"] == request_id
            started = time.monotonic()
            confirmation = client.post(f"/api/plans/{plan['planId']}/confirm",
                                       json={"context": CONTEXT, "planVersion": plan["version"]})
            confirm_ms = int((time.monotonic() - started) * 1000)
            assert confirmation.status_code == 200, confirmation.text
            body = confirmation.json()
            assert all(item["outcome"] == "succeeded" for item in body["results"])
            assert body["deviceState"]["version"] >= 3
            stop = client.post(f"/api/services/{body['service']['serviceId']}/stop", json={"context": CONTEXT})
            assert stop.status_code == 200
            reset = client.post("/api/demo/reset", params={"accountId": "demo-account"})
            assert reset.status_code == 200
            rows.append({
                "request_id": request_id, "plan_ms": plan_ms, "confirm_ms": confirm_ms,
                "agent_stages_ms": [{"agent": step["agent"], "title": step["title"],
                                     "latency_ms": step["latencyMs"]} for step in plan["trace"]],
                "plan_id": plan["planId"], "service_id": body["service"]["serviceId"],
                "action_ids": [item["actionId"] for item in body["results"]],
            })
    return {
        "mode": "in-process TestClient + rule planner + virtual gateway", "rounds": rounds,
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "plan_p50_ms": percentile([row["plan_ms"] for row in rows], 0.5),
        "plan_p95_ms": percentile([row["plan_ms"] for row in rows], 0.95),
        "confirm_p50_ms": percentile([row["confirm_ms"] for row in rows], 0.5),
        "confirm_p95_ms": percentile([row["confirm_ms"] for row in rows], 0.95),
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rounds", type=int, default=30)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.rounds < 1:
        parser.error("rounds must be positive")
    result = run(args.rounds)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print({key: value for key, value in result.items() if key != "rows"})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

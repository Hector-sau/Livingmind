"""Backend end-to-end check with the REAL model provider (no browser).

Path exercised: HTTP request -> identity check -> Planner -> Experience Agent -> DeepSeek
-> output validation -> deviation limit -> Plan -> confirm -> Executor -> virtual devices -> read back -> stop.

Run on a machine that has the key (never commit it):
    cd backend
    set -a && source .env && set +a
    .venv/bin/python scripts/e2e_real_model.py            # 5 requests
    .venv/bin/python scripts/e2e_real_model.py --rounds 2 # 10 requests

Prints per-request latency (server side, submit -> plan returned) and a summary.
Never prints the API key. Exit code 0 = invariants held and at least one model plan was produced.
"""

from __future__ import annotations

import argparse
import statistics
import sys
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore", category=DeprecationWarning)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app import config  # noqa: E402
from app.clock import utc_now  # noqa: E402
from app.main import create_app  # noqa: E402
from app.services.planner import Planner, provider_from_config  # noqa: E402
from app.services.rest_service import RestService, get_rest_service  # noqa: E402

TARGET_MS = 8000
SPACE = "space-home-bedroom"
CASES = [
    ("person-lin", "我想休息"),
    ("person-lin", "我想休息，有点热"),
    ("person-lin", "想早点睡，灯再暗一点"),
    ("person-chen", "我想休息"),
    ("person-chen", "有点冷，想休息了"),
]


def ctx(person: str) -> dict:
    return {"accountId": "demo-account", "personId": person, "spaceId": SPACE}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rounds", type=int, default=1)
    args = parser.parse_args()

    provider = provider_from_config()
    if provider is None:
        print("模型未配置：先在 backend/.env 填 DEEPSEEK_API_KEY，再运行 `set -a && source .env && set +a`。")
        return 2
    print(f"provider={provider.name} model={provider.model} timeout={config.MODEL_TIMEOUT_S:g}s base_url={config.DEEPSEEK_BASE_URL}")

    service = RestService(planner=Planner("model", provider, config.MODEL_TIMEOUT_S, utc_now))
    app = create_app()
    app.dependency_overrides[get_rest_service] = lambda: service
    client = TestClient(app)

    rows = []
    failures: list[str] = []
    before = client.get(f"/api/spaces/{SPACE}/devices", params={"accountId": "demo-account"}).json()

    for _ in range(args.rounds):
        for person, utterance in CASES:
            t0 = time.monotonic()
            res = client.post("/api/plans/rest", json={"context": ctx(person), "utterance": utterance, "mode": "model"})
            wall_ms = int((time.monotonic() - t0) * 1000)
            if res.status_code != 200:
                failures.append(f"{utterance}: HTTP {res.status_code}")
                continue
            plan = res.json()
            values = [a["value"] for a in plan["actions"]]
            rows.append((person, utterance, plan, values, wall_ms))
            # invariants
            if plan["source"] not in ("model", "rule_fallback"):
                failures.append(f"{utterance}: unexpected source {plan['source']}")
            if plan["source"] == "rule_fallback" and not plan["generation"]["fallbackReason"]:
                failures.append(f"{utterance}: fallback without reason")
            if plan["personId"] != person:
                failures.append(f"{utterance}: plan belongs to {plan['personId']}")

    after_plans = client.get(f"/api/spaces/{SPACE}/devices", params={"accountId": "demo-account"}).json()
    if after_plans["version"] != before["version"]:
        failures.append("devices changed while only creating plans")

    print()
    print(f"{'人物':<12}{'来源':<15}{'耗时ms':>8}  设置(灯/温/帘)   说明")
    for person, utterance, plan, values, wall_ms in rows:
        g = plan["generation"]
        note = plan["summary"] if plan["source"] == "model" else f"降级：{g['fallbackReason']}"
        print(f"{person:<12}{plan['source']:<15}{wall_ms:>8}  {values!s:<16} 「{utterance}」 {note}")

    model_rows = [r for r in rows if r[2]["source"] == "model"]
    if model_rows:
        lat = [r[4] for r in model_rows]
        print()
        print(f"模型计划 {len(model_rows)}/{len(rows)}；耗时 最小 {min(lat)} / 中位 {int(statistics.median(lat))} / 最大 {max(lat)} ms；"
              f"{'全部' if max(lat) <= TARGET_MS else '并非全部'}在 {TARGET_MS} ms 内")

        # confirm one model plan through the executor and check read-back, then stop
        plan = model_rows[0][2]
        res = client.post(f"/api/plans/{plan['planId']}/confirm", json={"context": ctx(plan["personId"]), "planVersion": 1}).json()
        outcomes = [r["outcome"] for r in res["results"]]
        state = res["deviceState"]
        observed = [state["lightBrightness"], state["acTargetTempC"], state["curtainOpenPercent"]]
        if outcomes != ["succeeded"] * 3 or [float(v) for v in observed] != [float(v) for v in model_rows[0][3]]:
            failures.append(f"confirm/read-back mismatch: {outcomes} {observed}")
        stop = client.post(f"/api/services/{res['service']['serviceId']}/stop", json={"context": ctx(plan["personId"])})
        if stop.status_code != 200:
            failures.append("stop failed")
        print(f"确认并执行第一个模型计划：{outcomes}，回读 {observed}；停止：HTTP {stop.status_code}")
    else:
        failures.append("no model plan produced (all requests fell back)")

    print()
    if failures:
        print("FAILED:", *failures, sep="\n  ")
        return 1
    print("OK：不变量全部成立")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

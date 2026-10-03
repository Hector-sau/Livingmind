"""Bounded paired DeepSeek comparison through a loopback HTTP API.

40 calls maximum by default (10 fixed cases x 2 variants x 2 repetitions).
Uses the same model/prompt/settings in both variants; alternates the order. Measures
HTTP API + model network time, not tablet latency or physical execution. AI-authored
cases are exploratory, not a human-reviewed independent accuracy benchmark.
"""

import argparse
from contextlib import ExitStack
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import sys
import time
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
from dotenv import dotenv_values

from app import config
from app.agents.experience.evaluation import score_case
from app.agents.experience.provider import DeepSeekProvider
from app.clock import utc_now
from app.contracts import Plan
from app.demo import seed
from app.main import create_app
from app.memory.repository import InMemoryPreferenceRepository
from app.repositories.store import MemoryStore
from app.services.planner import Planner
from app.services.rest_service import RestService, get_rest_service
from scripts.http_plan_bench import quantile, serve

CASES = [
    ("a01", "person-lin", "今晚打算休息，沿用我的偏好", "same", "same", "same"),
    ("a02", "person-chen", "我要休息，按我平常的设置", "same", "same", "same"),
    ("a03", "person-zhou", "准备睡了，按我的习惯设置", "same", "same", "same"),
    ("a04", "person-guest", "想休息了，使用默认设置", "same", "same", "same"),
    ("a05", "person-lin", "想休息，空调比平常调凉一些", "same", "lower", "same"),
    ("a06", "person-chen", "想休息，空调比平常调暖一些", "same", "higher", "same"),
    ("a07", "person-zhou", "想休息，灯光比平常暗一点", "lower", "same", "same"),
    ("a08", "person-lin", "想休息，灯光比平常亮一些", "higher", "same", "same"),
    ("a09", "person-chen", "想休息，窗帘比平常打开一些", "same", "same", "higher"),
    ("a10", "person-chen", "想休息，窗帘完全关上", "same", "same", "lower"),
]


def service_dependency(service):
    # No default arguments: FastAPI treats them as request parameters and attempts
    # to deepcopy RestService's locks. Each closure belongs to one comparison app.
    return lambda: service


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-calls", type=int, default=40)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.max_calls != 40:
        parser.error("This fixed protocol requires an explicit 40-call budget")
    # Read only the project provider configuration; never log it or evaluate shell code.
    local = dotenv_values(Path(__file__).resolve().parents[1] / ".env")
    key = config.DEEPSEEK_API_KEY or local.get("DEEPSEEK_API_KEY")
    if not key:
        parser.error("No local DeepSeek key is configured")
    base_url = local.get("DEEPSEEK_BASE_URL") or config.DEEPSEEK_BASE_URL
    model = local.get("DEEPSEEK_MODEL") or config.DEEPSEEK_MODEL
    config.DATABASE_URL, config.REDIS_URL, config.ORCHESTRATOR = "", "", "legacy"
    for name in ("livingmind.http", "livingmind.events"):
        for handler in logging.getLogger(name).handlers:
            handler.setLevel(logging.CRITICAL)
    people = {p.person_id: p for p in seed.PERSONS}
    rows = []
    result = {"recorded_at_utc": datetime.now(timezone.utc).isoformat(), "model": model,
              "scope": "loopback HTTP API + real DeepSeek; memory store; no device execution",
              "synthetic": True, "human_reviewed": False, "dataset": "exploratory-v3-ten-cases",
              "timeout_s": 6, "temperature": .3, "max_tokens": 2000, "call_budget": 40,
              "order": "alternated by case and repetition; no warm-up calls", "rows": rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)

    def save():
        summaries = []
        for variant in ("fresh", "pooled"):
            chosen = [r for r in rows if r["variant"] == variant]
            times = [r["wall_ms"] for r in chosen]
            summaries.append({"variant": variant, "requests": len(chosen),
                              "pass": sum(r["verdict"] == "pass" for r in chosen),
                              "fail": sum(r["verdict"] == "fail" for r in chosen),
                              "fallback": sum(r["verdict"] == "fallback" for r in chosen),
                              "clarification": sum(r["verdict"] == "clarification" for r in chosen),
                              "errors": sum(r["verdict"] == "error" for r in chosen),
                              "p50_ms": quantile(times, .5), "p95_ms": quantile(times, .95),
                              "usage_reported_count": sum(r["usage"] is not None for r in chosen)})
        result["summary"] = summaries
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    with ExitStack() as stack:
        clients, usages = {}, {}
        for pooled in (False, True):
            variant = "pooled" if pooled else "fresh"
            usages[variant] = []
            provider = DeepSeekProvider(key, model, base_url, 2000, usage_sink=usages[variant].append,
                                        reuse_connections=pooled)
            stack.callback(provider.close)
            svc = RestService(planner=Planner("model", provider, 6, utc_now),
                              store=MemoryStore(), preferences=InMemoryPreferenceRepository())
            app = create_app()
            app.dependency_overrides[get_rest_service] = service_dependency(svc)
            url = stack.enter_context(serve(app))
            clients[variant] = stack.enter_context(httpx.Client(base_url=url, timeout=15))
            # Fail infrastructure setup before making ANY paid request.
            clients[variant].get("/api/bootstrap", params={"accountId": "demo-account"}).raise_for_status()
        for repeat in range(2):
            for index, (case_id, person, utterance, light, ac, curtain) in enumerate(CASES):
                case = {"id": case_id, "expect": {"light": light, "ac": ac, "curtain": curtain}}
                order = ("fresh", "pooled") if (index + repeat) % 2 == 0 else ("pooled", "fresh")
                for variant in order:
                    if len(rows) >= args.max_calls:
                        raise RuntimeError("call budget exceeded")
                    count = len(usages[variant])
                    request_id = uuid.uuid4().hex
                    start = time.perf_counter()
                    verdict, source, details = "error", None, []
                    try:
                        response = clients[variant].post("/api/assistant/messages", headers={"X-Request-ID": request_id}, json={
                            "context": {"accountId": "demo-account", "personId": person, "spaceId": seed.DEFAULT_SPACE_ID},
                            "text": utterance, "mode": "model", "conversationId": request_id,
                        })
                        response.raise_for_status()
                        reply = response.json()
                        if reply["kind"] == "clarification":
                            verdict, details = "clarification", [reply["text"]]
                        elif reply.get("plan"):
                            plan = Plan.model_validate(reply["plan"])
                            score = score_case(case, people[person].rest_preference, plan)
                            verdict, source, details = score.verdict, plan.source, score.details
                    except (httpx.HTTPError, ValueError, KeyError) as exc:
                        details = [type(exc).__name__]  # no URL, headers or credentials
                    rows.append({"id": case_id, "repeat": repeat, "variant": variant,
                                 "request_id": request_id, "person": person, "utterance": utterance,
                                 "expected": case["expect"], "verdict": verdict, "source": source,
                                 "wall_ms": round((time.perf_counter() - start) * 1000, 3), "details": details,
                                 "usage": usages[variant][-1] if len(usages[variant]) > count else None})
                    save()  # preserve completed calls even if interrupted
                    print(f"{len(rows)}/40 {case_id} {variant}: {verdict} {rows[-1]['wall_ms']}ms", flush=True)
                    if verdict == "error":
                        print("Stopped after an infrastructure error; completed rows preserved.", flush=True)
                        return 1
    print(json.dumps(result["summary"], ensure_ascii=False))
    return 0 if all(r["verdict"] != "error" for r in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())

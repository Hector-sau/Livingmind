"""Run a labelled synthetic set. No model call unless --model is given.

    cd backend
    python scripts/evaluate_holdout.py
    python scripts/evaluate_holdout.py --dataset evals/holdout_v2.json --model --output evals/results/holdout-chat.json

The route and semantic metrics are separate; a schema-valid or fallback plan is not
silently counted as semantically correct. router_challenge_v1 was used to fix two bugs.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import config  # noqa: E402
from app.agents.experience.evaluation import score_case  # noqa: E402
from app.agents.orchestrator.agent import route_intent  # noqa: E402
from app.clock import utc_now  # noqa: E402
from app.contracts import RequestContext  # noqa: E402
from app.demo import seed  # noqa: E402
from app.services.planner import Planner, provider_from_config  # noqa: E402
from app.services.rest_service import RestService  # noqa: E402
from app.repositories.store import MemoryStore  # noqa: E402
from app.memory.repository import InMemoryPreferenceRepository  # noqa: E402

CASES_PATH = Path(__file__).resolve().parents[1] / "evals" / "router_challenge_v1.json"
PERSONS = {person.person_id: person for person in seed.PERSONS}
SPACE = "space-home-bedroom"


def percentile(values: list[int], fraction: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, min(len(ordered) - 1, int(len(ordered) * fraction + 0.999999) - 1))]


def run(cases: list[dict], service: RestService | None = None, dataset: str = "router_challenge_v1") -> dict:
    routes = []
    semantics = []
    for case in cases:
        predicted = route_intent(case["utterance"])
        routes.append({"id": case["id"], "expected": case["intent"], "actual": predicted, "correct": predicted == case["intent"]})
        if service is None or case["intent"] != "rest":
            continue
        context = RequestContext(account_id="demo-account", person_id=case["person"], space_id=SPACE)
        started = time.monotonic()
        plan = service.create_rest_plan(context, case["utterance"], "model")
        wall_ms = int((time.monotonic() - started) * 1000)
        score = score_case(case, PERSONS[case["person"]].rest_preference, plan)
        semantics.append({
            "id": case["id"], "verdict": score.verdict, "source": plan.source,
            "wall_ms": wall_ms, "details": score.details,
            "fallback_reason": plan.generation.fallback_reason,
        })
    timings = [item["wall_ms"] for item in semantics]
    return {
        "dataset": dataset, "synthetic": True,
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "route": {"correct": sum(item["correct"] for item in routes), "total": len(routes), "rows": routes},
        "semantic": {
            "pass": sum(item["verdict"] == "pass" for item in semantics),
            "fail": sum(item["verdict"] == "fail" for item in semantics),
            "fallback": sum(item["verdict"] == "fallback" for item in semantics),
            "total": len(semantics), "p50_ms": percentile(timings, 0.5), "p95_ms": percentile(timings, 0.95),
            "rows": semantics,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", action="store_true", help="call the configured real model for each rest request")
    parser.add_argument("--dataset", type=Path, default=CASES_PATH, help="labelled JSON; default is the development regression set")
    parser.add_argument("--output", type=Path, help="write machine-readable results to this path")
    args = parser.parse_args()
    cases = json.loads(args.dataset.read_text(encoding="utf-8"))["cases"]
    service = None
    provider = None
    if args.model:
        provider = provider_from_config()
        if provider is None:
            parser.error("--model requires a configured provider and DEEPSEEK_API_KEY")
        service = RestService(
            planner=Planner("model", provider, config.MODEL_TIMEOUT_S, utc_now),
            store=MemoryStore(), preferences=InMemoryPreferenceRepository(),
        )
    result = run(cases, service, args.dataset.stem)
    result["provider"] = provider.name if provider else None
    result["model"] = provider.model if provider else None
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    route, semantic = result["route"], result["semantic"]
    print(f"route {route['correct']}/{route['total']}; model semantics {semantic['pass']}/{semantic['total']} pass, "
          f"{semantic['fallback']} fallback; P50/P95 {semantic['p50_ms']}/{semantic['p95_ms']} ms")
    for item in route["rows"]:
        if not item["correct"]:
            print(f"route mismatch {item['id']}: {item['expected']} -> {item['actual']}")
    return 0 if route["correct"] == route["total"] and semantic["fail"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

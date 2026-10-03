"""Sequential paired benchmark on the sealed synthetic rest cases.

Same cases, prompt, timeout, temperature and output budget; alternate call order by
case to reduce time-of-day bias. This is a small exploratory comparison, not a claim
about production traffic or statistical significance. The real-model key stays local.
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
from app.agents.experience.provider import DeepSeekProvider  # noqa: E402
from app.clock import utc_now  # noqa: E402
from app.contracts import RequestContext  # noqa: E402
from app.demo import seed  # noqa: E402
from app.memory.repository import InMemoryPreferenceRepository  # noqa: E402
from app.repositories.store import MemoryStore  # noqa: E402
from app.services.planner import Planner  # noqa: E402
from app.services.rest_service import RestService  # noqa: E402
from scripts.evaluate_holdout import percentile  # noqa: E402

DATASET = Path(__file__).resolve().parents[1] / "evals" / "holdout_v2.json"
PERSONS = {person.person_id: person for person in seed.PERSONS}


def summarize(rows: list[dict], model: str) -> dict:
    chosen = [row for row in rows if row["model"] == model]
    lat = [row["wall_ms"] for row in chosen]
    return {
        "model": model, "total": len(chosen),
        "semantic_pass": sum(row["verdict"] == "pass" for row in chosen),
        "semantic_fail": sum(row["verdict"] == "fail" for row in chosen),
        "fallback": sum(row["verdict"] == "fallback" for row in chosen),
        "clarification": sum(row["verdict"] == "clarification" for row in chosen),
        "p50_ms": percentile(lat, 0.5), "p95_ms": percentile(lat, 0.95),
        "total_tokens_reported": sum((row["usage"] or {}).get("total_tokens") or 0 for row in chosen),
        "usage_reported_count": sum(row["usage"] is not None for row in chosen),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", nargs=2, default=["deepseek-chat", "deepseek-flash"])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not config.DEEPSEEK_API_KEY:
        parser.error("DEEPSEEK_API_KEY is required")
    cases = [case for case in json.loads(DATASET.read_text(encoding="utf-8"))["cases"] if case["intent"] == "rest"]
    rows: list[dict] = []
    for index, case in enumerate(cases):
        for model in (args.models if index % 2 == 0 else args.models[::-1]):
            usage: list[dict] = []
            provider = DeepSeekProvider(
                config.DEEPSEEK_API_KEY, model, config.DEEPSEEK_BASE_URL,
                config.MODEL_MAX_TOKENS, usage_sink=usage.append,
            )
            service = RestService(
                planner=Planner("model", provider, config.MODEL_TIMEOUT_S, utc_now),
                store=MemoryStore(), preferences=InMemoryPreferenceRepository(),
            )
            context = RequestContext(account_id="demo-account", person_id=case["person"], space_id="space-home-bedroom")
            start = time.monotonic()
            reply = service.handle_message(context, case["utterance"], "model", force_rest=True,
                                           conversation_id=f"comparison-{case['id']}")
            elapsed = int((time.monotonic() - start) * 1000)
            plan = reply.plan
            score = score_case(case, PERSONS[case["person"]].rest_preference, plan) if plan else None
            rows.append({
                "case_id": case["id"], "model": model, "source": plan.source if plan else None,
                "verdict": score.verdict if score else "clarification", "wall_ms": elapsed,
                "fallback_reason": plan.generation.fallback_reason if plan else None,
                "usage": usage[-1] if usage else None,
            })
            provider.close()
            print(f"{case['id']} {model} {rows[-1]['verdict']} {elapsed}ms", flush=True)
    result = {
        "dataset": DATASET.name, "synthetic": True, "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "order": "alternated per case", "timeout_s": config.MODEL_TIMEOUT_S,
        "max_tokens": config.MODEL_MAX_TOKENS, "temperature": 0.3,
        "summary": [summarize(rows, model) for model in args.models], "rows": rows,
    }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

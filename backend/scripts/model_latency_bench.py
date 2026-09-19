"""Repeated real Experience Agent calls, to replace a single latency sample with a distribution.

Run it on a machine that has the key. The key is read from the environment and never printed,
logged or written to the result file.

    cd backend && set -a && source .env && set +a \
      && .venv/bin/python scripts/model_latency_bench.py --samples 24

What this measures: `ExperienceAgent.plan()` — the same call the product makes, including JSON
parsing and schema validation, not a bare HTTP ping. A call that comes back well-formed but with
an out-of-range value counts as a `schema` failure here, exactly as it would in production.

What this does NOT measure: the rest of the request (rules, harness, executor), which is local
and sub-millisecond, or any concurrency — calls are sequential, like one person talking.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import config  # noqa: E402
from app.agents.experience import ExperienceAgent, ExperienceError  # noqa: E402
from app.clock import utc_now  # noqa: E402
from app.contracts import DeviceState  # noqa: E402
from app.demo import seed  # noqa: E402
from app.services.planner import provider_from_config  # noqa: E402

# The demo's own utterances, so the prompt distribution is the one the judges will see:
# a plain request, a request with a reason, a comparative, a vague one, and an off-topic one.
UTTERANCES = [
    "我想休息",
    "我想休息，有点热",
    "想早点睡，灯再暗一点",
    "把那个弄一下",
    "今天股市怎么样",
]


def percentile(values: list[int], q: float) -> int:
    """Nearest-rank percentile. With few samples this is the honest reading; no interpolation."""
    if not values:
        return 0
    ordered = sorted(values)
    rank = max(1, min(len(ordered), int(-(-q * len(ordered) // 1))))
    return ordered[rank - 1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=int, default=24, help="total calls (default 24)")
    parser.add_argument(
        "--timeout",
        type=float,
        default=config.MODEL_TIMEOUT_S,
        help="per-call budget in seconds; defaults to the production value so the fallback rate is the real one",
    )
    parser.add_argument("--gap", type=float, default=0.5, help="seconds between calls (default 0.5)")
    parser.add_argument(
        "--out",
        default="docs/evidence/model-latency.json",
        help="relative paths resolve against the repository root",
    )
    args = parser.parse_args()

    provider = provider_from_config()
    if provider is None:
        print("模型未配置：先在 backend/.env 填 DEEPSEEK_API_KEY，再运行 `set -a && source .env && set +a`。")
        return 2

    host = urlparse(config.DEEPSEEK_BASE_URL).hostname or "?"
    print(f"provider={provider.name} model={provider.model} host={host} timeout={args.timeout:g}s samples={args.samples}")
    print("跑的是真实网络调用，中途 Ctrl-C 会丢掉本次结果。\n")

    state = DeviceState(
        space_id=seed.DEFAULT_SPACE_ID,
        **seed.INITIAL_DEVICE_STATE,
        source="virtual_device",
        version=0,
        updated_at=utc_now(),
    )
    agent = ExperienceAgent(provider, args.timeout)

    rows: list[dict] = []
    for i in range(args.samples):
        person = seed.PERSONS[i % len(seed.PERSONS)]
        utterance = UTTERANCES[i % len(UTTERANCES)]
        try:
            result = agent.plan(person, state, utterance)
        except ExperienceError as exc:
            rows.append(
                {
                    "i": i + 1,
                    "person": person.person_id,
                    "utterance": utterance,
                    "outcome": exc.kind,
                    "latency_ms": exc.latency_ms,
                    "needs_clarification": None,
                }
            )
            print(f"{i + 1:>3}. {exc.kind:<14} {exc.latency_ms:>6} ms  {utterance}")
        else:
            rows.append(
                {
                    "i": i + 1,
                    "person": person.person_id,
                    "utterance": utterance,
                    "outcome": "ok",
                    "latency_ms": result.latency_ms,
                    "needs_clarification": bool(result.output.needs_clarification),
                }
            )
            flag = " ?" if result.output.needs_clarification else ""
            print(f"{i + 1:>3}. ok             {result.latency_ms:>6} ms  {utterance}{flag}")
        if i + 1 < args.samples:
            time.sleep(args.gap)

    ok = [r["latency_ms"] for r in rows if r["outcome"] == "ok"]
    failures: dict[str, int] = {}
    for r in rows:
        if r["outcome"] != "ok":
            failures[r["outcome"]] = failures.get(r["outcome"], 0) + 1

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "provider": provider.name,
        "model": provider.model,
        "host": host,
        "timeout_s": args.timeout,
        "samples": len(rows),
        "ok": len(ok),
        "success_rate": round(len(ok) / len(rows), 4) if rows else 0.0,
        "fallback_rate": round((len(rows) - len(ok)) / len(rows), 4) if rows else 0.0,
        "latency_ms": {
            "p50": percentile(ok, 0.50),
            "p90": percentile(ok, 0.90),
            "p95": percentile(ok, 0.95),
            "max": max(ok) if ok else 0,
            "mean": int(statistics.fmean(ok)) if ok else 0,
        },
        "failures_by_kind": failures,
        "needs_clarification": sum(1 for r in rows if r["needs_clarification"]),
    }

    repo = Path(__file__).resolve().parents[2]
    out = Path(args.out)
    out = (out if out.is_absolute() else repo / out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"summary": summary, "calls": rows}, ensure_ascii=False, indent=2) + "\n")

    print("\n| 指标 | 值 |")
    print("| --- | --- |")
    print(f"| 样本数 | {summary['samples']} |")
    print(f"| 成功 / 回退到规则 | {summary['ok']} / {summary['samples'] - summary['ok']} |")
    print(f"| 成功率 | {summary['success_rate'] * 100:.1f}% |")
    print(f"| p50 | {summary['latency_ms']['p50']} ms |")
    print(f"| p90 | {summary['latency_ms']['p90']} ms |")
    print(f"| p95 | {summary['latency_ms']['p95']} ms |")
    print(f"| 最大 | {summary['latency_ms']['max']} ms |")
    if failures:
        print(f"| 失败分类 | {', '.join(f'{k} ×{v}' for k, v in sorted(failures.items()))} |")
    print(f"\n写入 {out}")
    print("口径：延迟统计只含成功调用；失败调用按 kind 单列，超时那条的耗时约等于预算本身。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

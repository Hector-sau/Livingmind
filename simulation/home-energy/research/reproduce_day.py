"""Re-run the supplied one-day comparison and write the reproduced numbers as JSON.

It imports the evaluation from ``plot_product_demo`` instead of copying it, so there is no
second implementation of the environment, the policies or the metrics. No training happens
and no model file is written.

    cd simulation/home-energy
    python -m venv .venv && .venv/bin/pip install -r requirements-research.txt
    MPLBACKEND=Agg .venv/bin/python research/reproduce_day.py

Output: data/reproduced-day-comparison.json — the reproduced KPIs next to the supplied ones,
with the absolute difference per metric. The App never reads this file at runtime.
"""

from __future__ import annotations

import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch

RESEARCH_DIR = Path(__file__).resolve().parent
ROOT = RESEARCH_DIR.parent
sys.path.insert(0, str(RESEARCH_DIR))

from plot_product_demo import (  # noqa: E402
    Arguments,
    calculate_metrics,
    calculate_operating_cost,
    get_device,
    load_trained_agent,
    run_episode,
)

PROVIDED = ROOT / "data" / "provided-day-comparison.json"
OUTPUT = ROOT / "data" / "reproduced-day-comparison.json"
# Rounding tolerance: the supplied figure reports two decimals.
TOLERANCE = 0.01


def evaluate() -> dict[str, dict[str, float]]:
    random.seed(42)
    np.random.seed(42)
    torch.manual_seed(42)

    args = Arguments()
    args.N = 1
    args.obs_dim_total = 7
    args.obs_dim_n = [7]
    args.action_dim_n = [3]
    args.max_action = 1.0

    agent = load_trained_agent(args, get_device())
    agent_history, agent_reward, agent_env = run_episode("agent", agent=agent)
    rule_history, rule_reward, rule_env = run_episode("rule")

    agent_metrics = calculate_metrics(agent_history, agent_reward, agent_env.dt_hours)
    rule_metrics = calculate_metrics(rule_history, rule_reward, rule_env.dt_hours)
    agent_costs = calculate_operating_cost(agent_env, agent_history)
    rule_costs = calculate_operating_cost(rule_env, rule_history)
    return {
        "daily_cost": {"rule": rule_costs["total_cost"], "matd3": agent_costs["total_cost"]},
        "grid_import": {"rule": rule_metrics["grid_import_kwh"], "matd3": agent_metrics["grid_import_kwh"]},
        "peak_import": {"rule": rule_metrics["peak_grid_import_kw"], "matd3": agent_metrics["peak_grid_import_kw"]},
        "comfort_violation": {
            "rule": rule_metrics["comfort_violation_fh"],
            "matd3": agent_metrics["comfort_violation_fh"],
        },
    }


def main() -> int:
    supplied = {m["key"]: m for m in json.loads(PROVIDED.read_text(encoding="utf-8"))["metrics"]}
    reproduced = evaluate()

    rows, worst = [], 0.0
    for key, values in reproduced.items():
        reference = supplied[key]
        for controller in ("rule", "matd3"):
            diff = abs(round(values[controller], 3) - reference[controller])
            worst = max(worst, diff)
            rows.append(
                {
                    "metric": key,
                    "label": reference["label"],
                    "unit": reference["unit"],
                    "controller": controller,
                    "supplied": reference[controller],
                    "reproduced": round(values[controller], 3),
                    "abs_diff": round(diff, 4),
                    "matches": diff <= TOLERANCE,
                }
            )

    result = {
        "source": "reproduced_in_this_repository",
        "reproducedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "seed": 42,
        "tolerance": TOLERANCE,
        "allMatch": all(row["matches"] for row in rows),
        "worstAbsDiff": round(worst, 4),
        "note": "同一预设日、同一权重、种子 42 的重跑结果；与图中数字的差异只来自两位小数取整。",
        "rows": rows,
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    for row in rows:
        mark = "OK  " if row["matches"] else "DIFF"
        print(f"{mark} {row['label']:<10} {row['controller']:<6} 图 {row['supplied']:>8} · 重跑 {row['reproduced']:>8} {row['unit']}")
    print(f"\n最大差值 {result['worstAbsDiff']}（容差 {TOLERANCE}）-> {'全部一致' if result['allMatch'] else '有不一致'}")
    print("written:", OUTPUT)
    return 0 if result["allMatch"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

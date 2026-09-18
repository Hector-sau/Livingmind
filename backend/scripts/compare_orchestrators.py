"""Run the same inputs through both orchestration paths and print the differences.

    cd backend && .venv/bin/python scripts/compare_orchestrators.py

Equivalence ignores ids, timestamps and latencies (see app/graph/compare.py); it compares
what the user and the devices see: intent, summary, notes, actions, night schedule, energy
advice and the agent sequence.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.contracts import RequestContext  # noqa: E402
from app.graph.compare import fingerprint_diff, plan_equivalent  # noqa: E402
from app.graph.runtime import GraphOrchestrator  # noqa: E402
from app.services.rest_service import RestService  # noqa: E402

CASES = [
    ("person-lin", "我想休息"),
    ("person-lin", "我想休息，有点热"),
    ("person-chen", "我想休息"),
    ("person-zhou", "想早点睡，灯再暗一点"),
    ("person-guest", "我想休息"),
]


def ctx(person: str) -> RequestContext:
    return RequestContext(account_id="demo-account", person_id=person, space_id="space-home-bedroom")


def main() -> int:
    failures = 0
    for person, utterance in CASES:
        legacy = RestService()
        graph = RestService()
        graph._agent = GraphOrchestrator(graph._legacy_agent, lambda space_id: graph._devices[space_id])
        left = legacy.create_rest_plan(ctx(person), utterance)
        right = graph.create_rest_plan(ctx(person), utterance)
        same = plan_equivalent(left, right)
        print(f"{'OK  ' if same else 'DIFF'} {person} · {utterance}")
        if not same:
            failures += 1
            for field, (a, b) in fingerprint_diff(left, right).items():
                print(f"       {field}:\n         legacy: {a}\n         graph : {b}")
    print("\nall equivalent" if not failures else f"\n{failures} case(s) differ")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

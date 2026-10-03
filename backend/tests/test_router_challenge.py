"""Development regression tests. v2 is a historical dataset now that its h26 failure
has informed a fix; its old labels and scores remain unchanged, not rebranded as a
fresh independent acceptance score. v3 is only an unreviewed candidate.
"""

import json
from pathlib import Path

from app.agents.orchestrator.agent import route_intent
from app.agents.experience.evaluation import load_cases
from app.demo import seed

EVALS = Path(__file__).resolve().parents[1] / "evals"


def _cases(name: str) -> list[dict]:
    return json.loads((EVALS / name).read_text(encoding="utf-8"))["cases"]


def test_development_challenge_regresses_routes_with_explicit_safety_policy_changes():
    cases = _cases("router_challenge_v1.json")
    assert len(cases) == 40
    # Preserve the historical labels/results. These three requests say not to change
    # one device, which a full overnight schedule cannot honour. The new policy asks
    # for a bounded command instead. This is a safety tradeoff, not an accuracy gain.
    clarified = {"r14", "r15", "r16"}
    for case in cases:
        assert route_intent(case["utterance"]) == ("clarification" if case["id"] in clarified else case["intent"])


def test_historical_acceptance_set_retains_its_schema_and_distinct_inputs():
    train = {case["utterance"] for case in load_cases()}
    challenge = {case["utterance"] for case in _cases("router_challenge_v1.json")}
    sealed = _cases("holdout_v2.json")
    assert len(sealed) == 30
    assert len({case["id"] for case in sealed}) == len(sealed)
    assert len({case["utterance"] for case in sealed}) == len(sealed)
    assert {case["utterance"] for case in sealed}.isdisjoint(train | challenge)
    assert {case["person"] for case in sealed} == {person.person_id for person in seed.PERSONS}
    assert {case["intent"] for case in sealed} == {"rest", "device_command", "status", "clarification", "other"}
    assert all(set(case["expect"]) == {"light", "ac", "curtain"} for case in sealed if case["intent"] == "rest")

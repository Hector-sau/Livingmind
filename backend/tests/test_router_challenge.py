"""Development regression set. The untouched holdout_v2 is scored separately, not used for tuning."""

import json
from pathlib import Path

from app.agents.orchestrator.agent import route_intent
from app.agents.experience.evaluation import load_cases
from app.demo import seed

EVALS = Path(__file__).resolve().parents[1] / "evals"


def _cases(name: str) -> list[dict]:
    return json.loads((EVALS / name).read_text(encoding="utf-8"))["cases"]


def test_development_challenge_regresses_all_forty_routes():
    cases = _cases("router_challenge_v1.json")
    assert len(cases) == 40
    assert [(case["id"], route_intent(case["utterance"])) for case in cases if route_intent(case["utterance"]) != case["intent"]] == []


def test_sealed_acceptance_set_is_distinct_and_valid_without_tuning_against_its_labels():
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

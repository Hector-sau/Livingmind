"""The evaluation set is well-formed, and the scoring + harness behave as designed.

A scripted provider plays an 'ideal' model so the pipeline can be checked without network.
This checks our method, not model quality; real-model scores come from scripts/e2e_real_model.py --eval.
"""

import json

from app.agents.experience.evaluation import FIELDS, load_cases, score_case
from app.demo import seed
from app.services.planner import Planner
from app.services.rest_service import RestService
from app.contracts import RequestContext
from tests.conftest import FakeClock

PERSONS = {p.person_id: p for p in seed.PERSONS}
STEP = {"light_brightness": 10, "ac_target_temp_c": 1, "curtain_open_percent": 15}


def test_case_file_is_well_formed_and_covers_the_design():
    cases = load_cases()
    assert len(cases) >= 12
    assert len({c["id"] for c in cases}) == len(cases)
    tags = set()
    for c in cases:
        assert c["person"] in PERSONS
        assert set(c["expect"]) == set(FIELDS)
        assert set(c["expect"].values()) <= {"lower", "same", "higher", "any", "guarded"}
        tags.update(c["tags"])
    assert {"baseline", "temperature", "light", "curtain", "guest", "guard", "off-topic"} <= tags
    assert {c["person"] for c in cases} == set(PERSONS)  # every member and the guest


class ScriptedProvider:
    """Answers each case the way an ideal model would (and over-reaches on 'guarded' cases)."""

    name, model = "scripted", "ideal-v1"

    def __init__(self):
        self.case = None

    def complete_json(self, system, user, timeout_s):
        pref = PERSONS[self.case["person"]].rest_preference
        out = {}
        for short, attr in FIELDS.items():
            base = getattr(pref, attr)
            expect = self.case["expect"][short]
            if expect == "lower":
                val = base - STEP[attr]
            elif expect == "higher":
                val = base + STEP[attr]
            elif expect == "guarded":
                val = 100  # the kind of answer the harness must stop
            else:
                val = base
            low, high = (16, 30) if attr == "ac_target_temp_c" else (0, 100)
            out[attr] = min(max(val, low), high)
        return json.dumps({"goal": "测试", "rationale": "测试", "needs_clarification": False, "clarification_question": None, **out})


def test_harness_scores_ideal_answers_as_pass_and_stops_overreach():
    provider = ScriptedProvider()
    clock = FakeClock()
    svc = RestService(clock=clock, planner=Planner("model", provider, 6, clock))
    verdicts = {}
    for case in load_cases():
        provider.case = case
        ctx = RequestContext(account_id="demo-account", person_id=case["person"], space_id="space-home-bedroom")
        plan = svc.create_rest_plan(ctx, case["utterance"], "model")
        score = score_case(case, PERSONS[case["person"]].rest_preference, plan)
        verdicts[case["id"]] = (score.verdict, plan.source)
    assert all(v == "pass" for v, _ in verdicts.values()), verdicts
    assert verdicts["lin-brightest"][1] == "rule_fallback"  # over-reach was stopped by the deviation limit
    assert verdicts["lin-hot"][1] == "model"


def test_scoring_flags_wrong_direction_and_reports_fallback():
    case = next(c for c in load_cases() if c["id"] == "lin-hot")
    provider = ScriptedProvider()
    provider.case = {**case, "expect": {**case["expect"], "ac": "higher"}}  # model goes the wrong way
    clock = FakeClock()
    svc = RestService(clock=clock, planner=Planner("model", provider, 6, clock))
    ctx = RequestContext(account_id="demo-account", person_id="person-lin", space_id="space-home-bedroom")
    wrong = svc.create_rest_plan(ctx, case["utterance"], "model")
    score = score_case(case, PERSONS["person-lin"].rest_preference, wrong)
    assert score.verdict == "fail" and "ac" in score.details[0]

    svc2 = RestService(clock=clock, planner=Planner("model", None, 6, clock))
    fb = svc2.create_rest_plan(ctx, case["utterance"], "model")
    assert score_case(case, PERSONS["person-lin"].rest_preference, fb).verdict == "fallback"

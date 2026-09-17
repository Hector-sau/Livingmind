from app.demo.seed import MEMBERSHIPS, PERSONS


def test_two_persons_have_different_rest_preferences():
    assert len(PERSONS) >= 2
    prefs = {p.rest_preference.model_dump_json() for p in PERSONS}
    assert len(prefs) == len(PERSONS)


def test_demo_account_membership_covers_seed_persons():
    members = MEMBERSHIPS["demo-account"]["persons"]
    assert {p.person_id for p in PERSONS} == members

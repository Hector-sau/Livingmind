import pytest
from scripts.dataset_review import cases_hash, require_review


def test_candidate_labels_cannot_be_used_as_acceptance():
    with pytest.raises(ValueError, match="Candidate"):
        require_review({"version": 3, "status": "candidate_not_accepted", "cases": []})


def test_historical_regression_sets_remain_runnable():
    require_review({"version": 2, "human_reviewed": False, "cases": []})


def reviewed():
    dataset = {"version": 3, "status": "accepted", "human_reviewed": True, "reviewer": "test fixture reviewer",
               "reviewed_at": "2026-10-03T10:00:00+08:00", "cases": [{"id": "test", "intent": "rest"}]}
    dataset["reviewed_cases_sha256"] = cases_hash(dataset)
    return dataset


@pytest.mark.parametrize("field,value", [("human_reviewed", False), ("reviewer", ""),
                                        ("reviewed_at", "2026-10-03"), ("reviewed_cases_sha256", "wrong")])
def test_missing_or_stale_review_is_rejected(field, value):
    data = reviewed()
    data[field] = value
    with pytest.raises(ValueError):
        require_review(data)


def test_hash_detects_label_changes_after_review():
    data = reviewed()
    require_review(data)
    data["cases"][0]["intent"] = "status"
    with pytest.raises(ValueError, match="differ"):
        require_review(data)

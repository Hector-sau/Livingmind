"""Bind a human review to exact cases. A hash is provenance, not a human signature."""
import hashlib
import json
from datetime import datetime


def cases_hash(dataset):
    return hashlib.sha256(json.dumps(dataset["cases"], ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":")).encode()).hexdigest()


def require_review(dataset):
    if dataset.get("status") == "candidate_not_accepted":
        raise ValueError("Candidate labels require human review; do not score or tune against this acceptance set")
    if dataset.get("version", 0) < 3:
        return  # Historical/development datasets remain runnable, explicitly not a new holdout.
    if (dataset.get("status") != "accepted" or dataset.get("human_reviewed") is not True
            or not str(dataset.get("reviewer") or "").strip()):
        raise ValueError("Version 3+ requires accepted status, human_reviewed=true and a real reviewer")
    try:
        reviewed = datetime.fromisoformat(dataset["reviewed_at"].replace("Z", "+00:00"))
        if reviewed.tzinfo is None:
            raise ValueError()
    except (KeyError, TypeError, ValueError, AttributeError):
        raise ValueError("Provide the actual timezone-aware human review timestamp") from None
    if dataset.get("reviewed_cases_sha256") != cases_hash(dataset):
        raise ValueError("Cases differ from the reviewed version; a new review is needed")

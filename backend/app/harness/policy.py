"""Harness pre-check at planning time. The executor repeats the same checks before every write."""

from __future__ import annotations

from app.contracts import DeviceAction
from app.harness.executor import validate_action


def precheck(actions: list[DeviceAction]) -> tuple[list[DeviceAction], list[str]]:
    """Split actions into allowed ones and readable violations."""
    allowed, problems = [], []
    for a in actions:
        reason = validate_action(a)
        if reason:
            problems.append(f"{a.label}：{reason}")
        else:
            allowed.append(a)
    return allowed, problems

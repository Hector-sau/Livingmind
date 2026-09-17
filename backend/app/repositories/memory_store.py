"""In-memory storage. Everything resets when the process restarts."""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import Optional

from app.contracts import ActionResult, ActivityRecord, Plan, Service


@dataclass
class PlanRecord:
    plan: Plan
    epoch: int  # space epoch at creation; a stop bumps the epoch and invalidates older plans
    results: list[ActionResult] = field(default_factory=list)
    service_id: Optional[str] = None


@dataclass
class MemoryStore:
    plans: dict[str, PlanRecord] = field(default_factory=dict)
    services: dict[str, Service] = field(default_factory=dict)
    activity: list[ActivityRecord] = field(default_factory=list)
    epochs: dict[str, int] = field(default_factory=dict)
    replanning: set[str] = field(default_factory=set)  # service ids with an adjustment in flight
    advancing: set[str] = field(default_factory=set)  # service ids with a clock advance in flight
    _counter: itertools.count = field(default_factory=lambda: itertools.count(1))

    def new_id(self, prefix: str) -> str:
        return f"{prefix}-{next(self._counter):05d}"

    def epoch(self, space_id: str) -> int:
        return self.epochs.get(space_id, 0)

    def active_service(self, space_id: str) -> Optional[Service]:
        for s in self.services.values():
            if s.space_id == space_id and s.status == "active":
                return s
        return None

    def clear(self) -> None:
        self.plans.clear()
        self.services.clear()
        self.activity.clear()
        self.epochs.clear()
        self.replanning.clear()
        self.advancing.clear()

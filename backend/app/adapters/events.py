"""Protocol for real sensor/base events; the demo HTTP injector remains explicitly simulated."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Literal, Protocol, runtime_checkable


@dataclass(frozen=True)
class EnvironmentEvent:
    event_id: str
    dedupe_key: str
    source: str
    space_id: str
    event_type: Literal["room_temperature_changed", "sleep_detected"]
    captured_at: datetime
    value: float | bool


@runtime_checkable
class EnvironmentEventAdapter(Protocol):
    def subscribe(self, handler: Callable[[EnvironmentEvent], None]) -> Callable[[], None]:
        """Register a handler and return an unsubscribe function."""
        ...

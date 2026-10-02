"""The event envelope every consumer sees.

One shape for all domain events, so a consumer can dedupe (``event_id``), trace a request
(``correlation_id``), keep order per space (``space_id``) and survive schema changes
(``schema_version``).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel
from app.observability.context import current_request_id

EventType = Literal[
    "plan.created",
    "plan.confirmed",
    "service.started",
    "service.adjusted",
    "service.stopped",
    "service.completed",
    "service.failed",
    "device.action.completed",
    "memory.preference.updated",
    "energy.mode.updated",
]

SCHEMA_VERSION = 1


class Envelope(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: EventType
    schema_version: int = SCHEMA_VERSION
    occurred_at: datetime
    account_id: str
    person_id: Optional[str] = None
    space_id: str
    aggregate_id: str
    correlation_id: Optional[str] = None
    payload: dict[str, Any] = Field(default_factory=dict)


def event(
    event_type: EventType,
    *,
    occurred_at: datetime,
    space_id: str,
    aggregate_id: str,
    account_id: str = "demo-account",
    person_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
    **payload: Any,
) -> Envelope:
    return Envelope(
        event_type=event_type,
        occurred_at=occurred_at,
        account_id=account_id,
        person_id=person_id,
        space_id=space_id,
        aggregate_id=aggregate_id,
        correlation_id=correlation_id or current_request_id(),
        payload=payload,
    )

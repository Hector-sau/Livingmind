from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

__all__ = [
    "Contract",
    "RestPreference",
    "Person",
    "Space",
    "DemoAccount",
    "RequestContext",
    "DeviceAction",
    "DeviceState",
    "Plan",
    "PlanGeneration",
    "PlannerInfo",
    "PlannerMode",
    "Service",
    "ActionResult",
    "InjectEventRequest",
    "EventResult",
    "EventType",
    "EventOutcome",
    "ActivityRecord",
    "CreateRestPlanRequest",
    "ConfirmPlanRequest",
    "StopServiceRequest",
    "BootstrapResponse",
    "ConfirmPlanResponse",
    "StopServiceResponse",
    "ActivityResponse",
    "ErrorBody",
    "ErrorResponse",
    "DataSource",
    "PlanSource",
    "PlanStatus",
    "ServiceStatus",
    "DeviceType",
    "DeviceCommand",
    "ActionOutcome",
    "ActivityKind",
    "ActivitySource",
    "ErrorCode",
]


class Contract(BaseModel):
    """Base model: snake_case in Python, camelCase on the wire."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


# ---- enums (string literals keep generated TS simple) ----

# Where a device state came from. Never mix these in demos without labelling.
DataSource = Literal["virtual_device", "frontend_mock"]
# Who produced a plan. "rule_fallback" = model mode was requested but the rule engine produced the plan.
PlanSource = Literal["rule", "model", "rule_fallback", "frontend_mock"]
PlannerMode = Literal["rule", "model"]
PlanStatus = Literal["proposed", "executed", "expired", "invalidated"]
ServiceStatus = Literal["active", "stopped"]
DeviceType = Literal["light", "ac", "curtain"]
DeviceCommand = Literal["set_brightness", "set_target_temperature", "set_open_percent"]
ActionOutcome = Literal["succeeded", "rejected", "failed", "skipped"]
ActivityKind = Literal[
    "plan_created",
    "plan_fallback",
    "event_received",
    "event_ignored",
    "service_adjusted",
    "plan_confirmed",
    "plan_confirm_repeated",
    "plan_rejected",
    "action_executed",
    "action_rejected",
    "service_stopped",
    "demo_reset",
]
ActivitySource = Literal[
    "user", "rule_engine", "experience_agent", "executor", "virtual_device", "system", "simulated_event", "frontend_mock"
]
EventType = Literal["room_temperature_changed"]
EventOutcome = Literal["adjusted", "ignored"]
ErrorCode = Literal[
    "VALIDATION_ERROR",
    "NOT_FOUND",
    "FORBIDDEN_CONTEXT",
    "PLAN_EXPIRED",
    "PLAN_INVALIDATED",
    "PLAN_VERSION_MISMATCH",
    "SERVICE_ALREADY_ACTIVE",
    "SERVICE_NOT_ACTIVE",
    "INTERNAL_ERROR",
]


# ---- people, spaces, identity ----


class RestPreference(Contract):
    light_brightness: int = Field(ge=0, le=100, description="Preferred light brightness, percent")
    ac_target_temp_c: float = Field(ge=16, le=30, description="Preferred AC set point, Celsius")
    curtain_open_percent: int = Field(ge=0, le=100, description="Preferred curtain opening, percent")


class Person(Contract):
    person_id: str
    name: str
    description: str
    rest_preference: RestPreference


class Space(Contract):
    space_id: str
    name: str


class DemoAccount(Contract):
    """Demo identity only. This is NOT authentication."""

    account_id: str
    display_name: str
    is_demo: bool


class RequestContext(Contract):
    """Who is acting, for whom, and where. Checked server-side against demo memberships."""

    account_id: str
    person_id: str
    space_id: str


# ---- devices, plans, services ----


class DeviceAction(Contract):
    action_id: str
    device: DeviceType
    command: DeviceCommand
    value: float
    label: str = Field(description="Human readable description shown in the app")


class DeviceState(Contract):
    space_id: str
    light_brightness: int
    ac_target_temp_c: float
    curtain_open_percent: int
    source: DataSource
    version: int = Field(description="Increments on every successful device write")
    updated_at: datetime


class PlanGeneration(Contract):
    """How the plan was produced. Shown in the app so sources are never confused."""

    mode_requested: PlannerMode
    provider: Optional[str] = Field(description="e.g. deepseek; null for rule plans")
    model: Optional[str] = Field(description="Model name actually called; null for rule plans")
    latency_ms: int = Field(description="Time from request to plan (server side)")
    fallback_reason: Optional[str] = Field(description="Why the rule engine was used instead of the model")
    goal: Optional[str] = Field(description="Experience goal stated by the model")


class Plan(Contract):
    plan_id: str
    version: int
    person_id: str
    space_id: str
    scenario: Literal["rest", "rest_adjustment"]
    source: PlanSource
    summary: str
    notes: list[str]
    utterance: str
    actions: list[DeviceAction]
    status: PlanStatus
    created_at: datetime
    expires_at: datetime
    generation: PlanGeneration


class Service(Contract):
    service_id: str
    space_id: str
    person_id: str
    plan_id: str
    plan_version: int
    status: ServiceStatus
    started_at: datetime
    stopped_at: Optional[datetime]
    planner_mode: PlannerMode = Field(description="Mode used for this service's plans; event re-planning follows it")
    adjustments: int = Field(description="Automatic adjustments made by events so far")
    last_adjusted_at: Optional[datetime]


class ActionResult(Contract):
    action_id: str
    device: DeviceType
    command: DeviceCommand
    value: float
    outcome: ActionOutcome
    reason: Optional[str]
    observed_value: Optional[float] = Field(description="Value read back from the device after the write")


class ActivityRecord(Contract):
    activity_id: str
    timestamp: datetime
    space_id: str
    kind: ActivityKind
    source: ActivitySource
    message: str
    service_id: Optional[str]
    plan_id: Optional[str]
    person_id: Optional[str]
    action: Optional[ActionResult]


# ---- requests ----


class CreateRestPlanRequest(Contract):
    context: RequestContext
    utterance: str = Field(min_length=1, max_length=200)
    mode: Optional[PlannerMode] = Field(default=None, description="null = server default")


class ConfirmPlanRequest(Contract):
    context: RequestContext
    plan_version: int


class StopServiceRequest(Contract):
    context: RequestContext


class InjectEventRequest(Contract):
    """Simulated environment event (demo only; there is no real sensor)."""

    context: RequestContext
    type: EventType
    room_temp_c: float = Field(ge=5, le=45)


# ---- responses ----


class PlannerInfo(Contract):
    default_mode: PlannerMode
    model_configured: bool = Field(description="A provider and key are configured server-side (not proof it works)")
    provider: Optional[str]
    model: Optional[str]
    timeout_ms: int


class BootstrapResponse(Contract):
    mode: Literal["demo"]
    planner: PlannerInfo
    account: DemoAccount
    persons: list[Person]
    spaces: list[Space]
    default_space_id: str
    device_state: DeviceState
    active_service: Optional[Service]


class ConfirmPlanResponse(Contract):
    plan: Plan
    service: Service
    results: list[ActionResult]
    device_state: DeviceState
    repeated: bool = Field(description="True when the plan was already executed; nothing was re-run")


class StopServiceResponse(Contract):
    service: Service
    device_state: DeviceState


class EventResult(Contract):
    event_id: str
    source: Literal["simulated"]
    outcome: EventOutcome
    reason: Optional[str] = Field(description="Why the event was ignored, if it was")
    service: Optional[Service]
    plan: Optional[Plan] = Field(description="The adjustment plan that was executed")
    results: list[ActionResult]
    device_state: DeviceState


class ActivityResponse(Contract):
    items: list[ActivityRecord]


class ErrorBody(Contract):
    code: ErrorCode
    message: str
    details: Optional[dict[str, Any]]


class ErrorResponse(Contract):
    error: ErrorBody

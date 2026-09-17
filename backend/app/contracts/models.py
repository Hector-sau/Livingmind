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
    "ScheduledStep",
    "SchedulePhase",
    "ScheduleStepStatus",
    "AdvanceClockRequest",
    "AdvanceClockResponse",
    "ActionResult",
    "AgentName",
    "AgentStep",
    "StepSource",
    "EnergyAdvice",
    "EnergyMode",
    "PowerTier",
    "AssistantMessageRequest",
    "AssistantReply",
    "MemoryView",
    "SpaceRule",
    "UpdatePreferenceRequest",
    "SetEnergyModeRequest",
    "Capability",
    "InjectEventRequest",
    "UnlockPersonRequest",
    "UnlockPersonResponse",
    "Scene",
    "SceneStatus",
    "ScenesResponse",
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
# completed = the overnight schedule finished (wake-up done); stopped = the user stopped it.
ServiceStatus = Literal["active", "stopped", "completed"]
SchedulePhase = Literal["sleep", "deep", "wake"]
ScheduleStepStatus = Literal["pending", "running", "done", "cancelled"]
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
    "memory_updated",
    "energy_mode_changed",
    "demo_reset",
    "clock_advanced",
    "schedule_step_executed",
    "schedule_cancelled",
    "service_completed",
]
ActivitySource = Literal[
    "user", "rule_engine", "experience_agent", "executor", "virtual_device", "system", "simulated_event", "simulated_clock", "frontend_mock"
]
EventType = Literal["room_temperature_changed"]
AgentName = Literal["orchestrator", "memory", "experience", "energy", "space_execution", "harness"]
StepSource = Literal["rule", "model", "rule_fallback", "frontend_mock"]
EnergyMode = Literal["comfort_first", "eco"]
PowerTier = Literal["low", "medium", "high"]
EventOutcome = Literal["adjusted", "ignored"]
ErrorCode = Literal[
    "NOT_EDITABLE",
    "VALIDATION_ERROR",
    "NOT_FOUND",
    "FORBIDDEN_CONTEXT",
    "PLAN_EXPIRED",
    "PLAN_INVALIDATED",
    "PLAN_VERSION_MISMATCH",
    "SERVICE_ALREADY_ACTIVE",
    "SERVICE_NOT_ACTIVE",
    "PIN_INVALID",
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
    rest_preference: Optional[RestPreference] = Field(
        default=None,
        description="Omitted in shared listings; read your own via the memory endpoint",
    )
    is_guest: bool = Field(description="Guest / shared-space context: space defaults, no personal profile")
    has_pin: bool = Field(description="A demo PIN guards switching to this person (the PIN itself is never sent)")
    avatar_color: str = Field(description="Display color for the avatar")


class Space(Contract):
    space_id: str
    name: str
    default_rest_preference: RestPreference
    energy_mode: EnergyMode = Field(description="comfort_first: advise only; eco: apply advice inside the comfort band")


class SpaceRule(Contract):
    """Shared rule of a space. Visible to everyone in the space (unlike personal preferences)."""

    rule_id: str
    text: str
    enforced: bool = Field(description="True when code enforces it (not just displayed)")


SceneStatus = Literal["implemented", "planned"]


class Scene(Contract):
    """Proactive-service scene shown in the app. Status must match the real implementation."""

    scene_id: str
    title: str
    description: str
    status: SceneStatus
    verification: str = Field(description="How the status was verified, shown to users")
    trigger: str


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


class AgentStep(Contract):
    """One step of the 1+2 agent collaboration, kept with the plan as call evidence."""

    agent: AgentName
    title: str
    detail: str
    source: StepSource
    latency_ms: int
    ok: bool


class EnergyAdvice(Contract):
    """Rule-based energy advice. Loads are rough rule estimates, not measurements."""

    mode: EnergyMode
    tariff: Literal["peak", "offpeak"]
    outdoor_temp_c: float
    comfort_min_c: float
    comfort_max_c: float
    requested_ac_c: float
    recommended_ac_c: float
    applied: bool = Field(description="True only in eco mode when the recommendation changed the set point")
    load_kw_before: float
    load_kw_after: float
    tier_before: PowerTier
    tier_after: PowerTier
    reason: str
    source: Literal["rule", "frontend_mock"]


class Capability(Contract):
    device: DeviceType
    command: DeviceCommand
    min: float
    max: float
    integer: bool


class ScheduledStep(Contract):
    """One timed step of the overnight schedule. Driven by a simulated clock, never by wall time."""

    step_id: str
    phase: SchedulePhase
    at: str = Field(description="Simulated local time, HH:MM")
    offset_min: int = Field(description="Minutes after the simulated night start")
    title: str
    actions: list[DeviceAction]
    status: ScheduleStepStatus = Field(description="running = claimed by one clock advance; a step runs at most once")
    executed_at: Optional[datetime]
    source: Literal["rule", "frontend_mock"]


class Plan(Contract):
    plan_id: str
    version: int
    person_id: str
    space_id: str
    scenario: Literal["rest", "rest_adjustment", "device_command"]
    source: PlanSource
    summary: str
    notes: list[str]
    utterance: str
    actions: list[DeviceAction]
    status: PlanStatus
    created_at: datetime
    expires_at: datetime
    generation: PlanGeneration
    trace: list[AgentStep] = Field(default_factory=list)
    energy: Optional[EnergyAdvice] = None
    schedule: list[ScheduledStep] = Field(description="Overnight schedule confirmed together with a rest plan; empty otherwise")


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
    night_clock: str = Field(description="Simulated local time of the overnight schedule, HH:MM")
    night_offset_min: int = Field(description="Simulated minutes since the night start")
    schedule: list[ScheduledStep]


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


class AdvanceClockRequest(Contract):
    """Move the simulated night clock. minutes=null jumps to the next pending step."""

    context: RequestContext
    minutes: Optional[int] = Field(default=None, ge=1, le=720)


class UnlockPersonRequest(Contract):
    """Demo PIN check before switching person on a shared tablet. NOT authentication."""

    account_id: str
    pin: Optional[str] = Field(default=None, max_length=8)


class UnlockPersonResponse(Contract):
    person_id: str
    unlocked: bool
    note: str


class AssistantMessageRequest(Contract):
    context: RequestContext
    text: str = Field(min_length=1, max_length=200)
    mode: Optional[PlannerMode] = None


class UpdatePreferenceRequest(Contract):
    context: RequestContext
    preference: RestPreference


class SetEnergyModeRequest(Contract):
    context: RequestContext
    mode: EnergyMode


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
    service: Optional[Service] = Field(description="Null for direct device commands (no rest service)")
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


class AdvanceClockResponse(Contract):
    service: Service
    executed: list[ScheduledStep] = Field(description="Steps that came due and ran during this advance")
    results: list[ActionResult]
    device_state: DeviceState
    note: Optional[str] = Field(description="Why nothing happened, if nothing did")


class AssistantReply(Contract):
    kind: Literal["plan", "answer"]
    intent: Literal["rest", "device_command", "status", "other"]
    text: str
    plan: Optional[Plan]
    trace: list[AgentStep]


class MemoryView(Contract):
    """What the requesting person may see: only their own preference plus shared space rules."""

    person_id: str
    is_guest: bool
    preference: RestPreference
    editable: bool
    updated_at: Optional[datetime]
    shared_rules: list[SpaceRule]


class ScenesResponse(Contract):
    items: list[Scene]


class ActivityResponse(Contract):
    items: list[ActivityRecord]


class ErrorBody(Contract):
    code: ErrorCode
    message: str
    details: Optional[dict[str, Any]]


class ErrorResponse(Contract):
    error: ErrorBody

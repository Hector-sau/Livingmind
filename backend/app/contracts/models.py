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
    "SimulateSleepRequest",
    "ActionResult",
    "ActionExecution",
    "ReconcileActionRequest",
    "ActionExecutionStatus",
    "PolicyDecision",
    "PolicyDecisionType",
    "PolicyRuleResult",
    "ExecutionGrant",
    "ExecutionGrantStatus",
    "AgentName",
    "AgentStep",
    "StepSource",
    "EnergyAdvice",
    "EnergyMode",
    "PowerTier",
    "OfflineEnergyMetric",
    "OfflineEnergyAsset",
    "OfflineEnergyProfilePoint",
    "OfflineEnergySimulation",
    "AssistantMessageRequest",
    "AssistantReply",
    "PendingClarification",
    "RecoveryStatus",
    "DeviceControlRequest",
    "DeviceControlResponse",
    "UndoWindow",
    "UndoRequest",
    "UndoResponse",
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
    "WakeTime",
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
ServiceStatus = Literal["active", "stopped", "completed", "failed"]
# The demo offers a small validated wake-time choice. Arbitrary calendar scheduling
# remains a later capability, rather than a misleading claim in the first release.
WakeTime = Literal["06:30", "07:00", "07:30"]
SchedulePhase = Literal["sleep", "deep", "wake"]
ScheduleStepStatus = Literal["pending", "running", "done", "cancelled"]
DeviceType = Literal["light", "ac", "curtain"]
DeviceCommand = Literal["set_brightness", "set_target_temperature", "set_open_percent"]
ActionOutcome = Literal["succeeded", "rejected", "failed", "skipped", "unknown"]
ActionExecutionStatus = Literal[
    "pending",
    "dispatching",
    "accepted",
    "completed",
    "rejected",
    "failed",
    "unknown",
    "cancelled",
]
PolicyDecisionType = Literal["allow", "deny", "require_confirmation"]
ExecutionGrantStatus = Literal["active", "revoked", "expired"]
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
    "service_failed",
    "clarification_requested",
    "clarification_resolved",
    "clarification_cancelled",
    "device_controlled",
    "device_control_undone",
]
ActivitySource = Literal[
    "user", "rule_engine", "experience_agent", "executor", "virtual_device", "system", "simulated_event", "simulated_clock", "frontend_mock"
]
EventType = Literal["room_temperature_changed"]
AgentName = Literal["orchestrator", "memory", "experience", "energy", "space_execution", "harness"]
StepSource = Literal["rule", "model", "rule_fallback", "frontend_mock"]
EnergyMode = Literal["comfort_first", "eco"]
PowerTier = Literal["low", "medium", "high"]
EnergyAssetRole = Literal["supply", "demand", "storage", "trading", "backup"]
EventOutcome = Literal["adjusted", "ignored"]
ErrorCode = Literal[
    "CLARIFICATION_REQUIRED",
    "NOT_EDITABLE",
    "VALIDATION_ERROR",
    "NOT_FOUND",
    "FORBIDDEN_CONTEXT",
    "PLAN_EXPIRED",
    "PLAN_INVALIDATED",
    "PLAN_VERSION_MISMATCH",
    "SERVICE_ALREADY_ACTIVE",
    "SERVICE_NOT_ACTIVE",
    "SPACE_BUSY",
    "PIN_INVALID",
    "UNDO_EXPIRED",
    "UNDO_INVALIDATED",
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


class PendingClarification(Contract):
    """A resumable question in one person/space conversation."""

    clarification_id: str
    conversation_id: str
    account_id: str
    person_id: str
    space_id: str
    original_text: str
    question: str
    target_intent: Literal["rest", "device_command"]
    created_at: datetime
    expires_at: datetime


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


class OfflineEnergyMetric(Contract):
    """A supplied one-day benchmark metric. It is not a real-time App measurement."""

    key: Literal["daily_cost", "grid_import", "peak_import", "comfort_violation"]
    label: str
    unit: str
    rule: float
    matd3: float
    lower_is_better: bool


class OfflineEnergyAsset(Contract):
    """A read-only asset represented by the offline energy simulation."""

    id: str
    name: str
    role: EnergyAssetRole
    control: str = Field(description="Explains whether this is an App control or offline simulation context")


class OfflineEnergyProfilePoint(Contract):
    hour: int = Field(ge=0, le=23)
    pv_kw: float
    wind_kw: float
    base_load_kw: float
    buy_price_usd_per_kwh: float
    outdoor_temp_f: float


class OfflineEnergySimulation(Contract):
    """Supplied fixed-day offline evidence; deliberately separate from online energy rules."""

    source: Literal["provided_precomputed_offline_simulation"]
    scenario: str
    controller: str
    agent_count: int = Field(ge=1)
    resolution: str
    metrics: list[OfflineEnergyMetric]
    assets: list[OfflineEnergyAsset]
    profile: list[OfflineEnergyProfilePoint]
    limits: list[str]


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
    wake_time: Optional[WakeTime] = Field(
        default=None, description="Requested simulated wake time; ignored by direct device commands"
    )


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
    wake_time: WakeTime = Field(default="07:00", description="Requested simulated wake time for this service")
    sleep_detected_at: Optional[datetime] = Field(
        default=None, description="Set only when the demo's explicit simulated-sleep event was used"
    )


class ActionResult(Contract):
    action_id: str
    device: DeviceType
    command: DeviceCommand
    value: float
    outcome: ActionOutcome
    reason: Optional[str]
    observed_value: Optional[float] = Field(description="Value read back from the device after the write")


class UndoWindow(Contract):
    """A short chance to put a device back exactly where it was.

    Low-risk device writes execute immediately and offer this instead of a confirmation
    dialog: on a control people touch dozens of times a day, a dialog trains them to
    dismiss it without reading. The window lives in the running process only — after a
    restart there is nothing to undo, which is the intended semantic, not an omission.
    """

    undo_id: str
    space_id: str
    device: DeviceType
    previous_value: float = Field(description="Exact value read back before the write; undo restores this")
    applied_value: float
    label: str
    expires_at: datetime


class DeviceControlRequest(Contract):
    """Direct control from the device panel. Still goes through the Harness executor."""

    context: "RequestContext"
    device: DeviceType
    value: float


class DeviceControlResponse(Contract):
    device_state: Optional["DeviceState"]
    result: "ActionResult"
    undo: Optional[UndoWindow] = Field(description="Null when the write did not succeed")
    warning: Optional[str] = None


class UndoRequest(Contract):
    context: "RequestContext"


class UndoResponse(Contract):
    device_state: Optional["DeviceState"]
    result: "ActionResult"
    restored_value: float
    warning: Optional[str] = None


class PolicyRuleResult(Contract):
    """One deterministic rule evaluated before a plan can receive execution authority."""

    rule: str
    passed: bool
    detail: str


class PolicyDecision(Contract):
    """Auditable Harness output. It explains why a plan may proceed to confirmation."""

    decision_id: str
    plan_id: str
    plan_version: int
    space_id: str
    policy_version: str
    decision: PolicyDecisionType
    plan_hash: str
    checks: list[PolicyRuleResult]
    reasons: list[str]
    decided_at: datetime


class ExecutionGrant(Contract):
    """Bounded, expiring authority created by confirmation; not a general device credential."""

    grant_id: str
    policy_decision_id: str
    account_id: str
    person_id: str
    space_id: str
    plan_id: str
    plan_version: int
    plan_hash: str
    service_id: Optional[str]
    service_epoch: int
    capabilities: list[Capability]
    max_adjustments: int = Field(ge=0)
    status: ExecutionGrantStatus
    created_at: datetime
    valid_until: datetime
    revoked_at: Optional[datetime] = None


class ActionExecution(Contract):
    """Durable command ledger entry, separate from the user-facing action result."""

    action_id: str
    grant_id: Optional[str]
    plan_id: Optional[str]
    account_id: Optional[str] = None
    person_id: Optional[str] = None
    source: Literal["plan", "manual", "undo"] = "plan"
    service_id: Optional[str]
    space_id: str
    device: DeviceType
    command: DeviceCommand
    requested_value: float
    service_epoch: int
    status: ActionExecutionStatus
    attempt_count: int = Field(ge=0)
    requested_at: datetime
    accepted_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    observed_value: Optional[float] = None
    observed_at: Optional[datetime] = None
    error_kind: Optional[str] = None
    error_detail: Optional[str] = None
    recovery_attempts: int = Field(default=0, ge=0)
    last_checked_at: Optional[datetime] = None
    next_check_at: Optional[datetime] = None
    recovery_exhausted: bool = False


class ReconcileActionRequest(Contract):
    context: RequestContext


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
    wake_time: Optional[WakeTime] = None


class ConfirmPlanRequest(Contract):
    context: RequestContext
    plan_version: int


class StopServiceRequest(Contract):
    context: RequestContext


class AdvanceClockRequest(Contract):
    """Move the simulated night clock. minutes=null jumps to the next pending step."""

    context: RequestContext
    minutes: Optional[int] = Field(default=None, ge=1, le=720)


class SimulateSleepRequest(Contract):
    """Explicit demo sleep signal; this is not a physical sensor integration."""

    context: RequestContext


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
    wake_time: Optional[WakeTime] = None
    conversation_id: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=120,
        description="Stable id for resuming a pending clarification; scoped again by account/person/space",
    )


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


class RecoveryStatus(Contract):
    """Result of the startup reconciliation; observable evidence, not a claim of exact device recovery."""

    store: Literal["memory", "postgresql"]
    active_services: int
    cancelled_unknown_steps: int
    cleared_inflight_flags: int
    unknown_actions: int = Field(default=0, description="Commands whose final device outcome needs reconciliation")
    device_state_reconciled: bool
    checked_at: datetime
    note: str


class ConfirmPlanResponse(Contract):
    plan: Plan
    service: Optional[Service] = Field(description="Null for direct device commands (no rest service)")
    results: list[ActionResult]
    device_state: DeviceState
    repeated: bool = Field(description="True when the plan was already executed; nothing was re-run")
    policy_decision: Optional[PolicyDecision] = Field(default=None, description="Harness decision for this confirmation")
    execution_grant: Optional[ExecutionGrant] = Field(default=None, description="Bounded authority created by confirmation")


class StopServiceResponse(Contract):
    service: Service
    device_state: Optional[DeviceState]
    warning: Optional[str] = None


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
    kind: Literal["plan", "answer", "clarification"]
    intent: Literal["rest", "device_command", "status", "other", "clarification"]
    text: str
    plan: Optional[Plan]
    trace: list[AgentStep]
    conversation_id: Optional[str] = None
    clarification: Optional[PendingClarification] = None


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

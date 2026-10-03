"""HTTP routes for the rest scenario. Handlers only translate HTTP <-> domain; logic lives in app/services."""

from fastapi import APIRouter, Depends, Query

from app.api.errors import ERROR_RESPONSES
from app.contracts import (
    ActionExecution,
    ReconcileActionRequest,
    ActivityResponse,
    AdvanceClockRequest,
    AdvanceClockResponse,
    AssistantMessageRequest,
    AssistantReply,
    MemoryView,
    OfflineEnergySimulation,
    SimulateSleepRequest,
    RequestContext,
    SetEnergyModeRequest,
    Space,
    UpdatePreferenceRequest,
    BootstrapResponse,
    ConfirmPlanRequest,
    ConfirmPlanResponse,
    CreateRestPlanRequest,
    DeviceState,
    EventResult,
    InjectEventRequest,
    DeviceControlRequest,
    DeviceControlResponse,
    Plan,
    RecoveryStatus,
    UndoRequest,
    UndoResponse,
    ScenesResponse,
    StopServiceRequest,
    UnlockPersonRequest,
    UnlockPersonResponse,
    StopServiceResponse,
)
from app.services.rest_service import RestService, get_rest_service

router = APIRouter(prefix="/api", responses=ERROR_RESPONSES)
Svc = Depends(get_rest_service)


@router.post("/actions/{action_id}/reconcile", response_model=ActionExecution,
             operation_id="reconcileAction", tags=["devices"])
def reconcile_action(action_id: str, body: ReconcileActionRequest, svc: RestService = Svc) -> ActionExecution:
    """Recheck an uncertain action's receipt without issuing another device command."""
    return svc.reconcile_action(action_id, body.context)


@router.get("/bootstrap", response_model=BootstrapResponse, operation_id="getBootstrap", tags=["demo"])
def get_bootstrap(account_id: str = Query(alias="accountId"), svc: RestService = Svc) -> BootstrapResponse:
    return svc.bootstrap(account_id)


@router.get("/system/recovery", response_model=RecoveryStatus, operation_id="getRecoveryStatus", tags=["system"])
def get_recovery_status(account_id: str = Query(alias="accountId"), svc: RestService = Svc) -> RecoveryStatus:
    return svc.recovery_status(account_id)


@router.post(
    "/persons/{person_id}/unlock", response_model=UnlockPersonResponse, operation_id="unlockPerson", tags=["demo"]
)
def unlock_person(person_id: str, body: UnlockPersonRequest, svc: RestService = Svc) -> UnlockPersonResponse:
    """Demo PIN check before switching person. Not authentication."""
    return svc.unlock_person(body.account_id, person_id, body.pin)


@router.get("/scenes", response_model=ScenesResponse, operation_id="getScenes", tags=["demo"])
def get_scenes(account_id: str = Query(alias="accountId"), svc: RestService = Svc) -> ScenesResponse:
    return ScenesResponse(items=svc.scenes(account_id))


@router.get("/spaces/{space_id}/devices", response_model=DeviceState, operation_id="getDeviceState", tags=["devices"])
def get_device_state(space_id: str, account_id: str = Query(alias="accountId"), svc: RestService = Svc) -> DeviceState:
    return svc.device_state(account_id, space_id)


@router.post(
    "/spaces/{space_id}/devices/control",
    response_model=DeviceControlResponse,
    operation_id="controlDevice",
    tags=["devices"],
)
def control_device(space_id: str, body: DeviceControlRequest, svc: RestService = Svc) -> DeviceControlResponse:
    """Direct control from the device panel: executes at once, then offers an undo window."""
    return svc.control_device(space_id, body.context, body.device, body.value)


@router.post("/devices/undo/{undo_id}", response_model=UndoResponse, operation_id="undoDeviceControl", tags=["devices"])
def undo_device_control(undo_id: str, body: UndoRequest, svc: RestService = Svc) -> UndoResponse:
    """Restore the exact value the device held before the write, while the window is open."""
    return svc.undo_device_control(undo_id, body.context)


@router.post("/assistant/messages", response_model=AssistantReply, operation_id="sendMessage", tags=["assistant"])
def send_message(body: AssistantMessageRequest, svc: RestService = Svc) -> AssistantReply:
    """Main Agent entry: routes the message and returns a plan (to confirm) or a short answer."""
    return svc.handle_message(
        body.context,
        body.text,
        body.mode,
        wake_time=body.wake_time or "07:00",
        conversation_id=body.conversation_id,
    )


@router.get("/memory", response_model=MemoryView, operation_id="getMemory", tags=["memory"])
def get_memory(
    account_id: str = Query(alias="accountId"),
    person_id: str = Query(alias="personId"),
    space_id: str = Query(alias="spaceId"),
    svc: RestService = Svc,
) -> MemoryView:
    """Only the acting person's own preference plus shared space rules."""
    return svc.memory_view(RequestContext(account_id=account_id, person_id=person_id, space_id=space_id))


@router.put("/memory/preference", response_model=MemoryView, operation_id="updatePreference", tags=["memory"])
def update_preference(body: UpdatePreferenceRequest, svc: RestService = Svc) -> MemoryView:
    return svc.update_preference(body.context, body.preference)


@router.put("/spaces/{space_id}/energy-mode", response_model=Space, operation_id="setEnergyMode", tags=["energy"])
def set_energy_mode(space_id: str, body: SetEnergyModeRequest, svc: RestService = Svc) -> Space:
    return svc.set_energy_mode(space_id, body.context, body.mode)


@router.get(
    "/spaces/{space_id}/energy/simulation",
    response_model=OfflineEnergySimulation,
    operation_id="getOfflineEnergySimulation",
    tags=["energy"],
)
def get_offline_energy_simulation(
    space_id: str, account_id: str = Query(alias="accountId"), svc: RestService = Svc
) -> OfflineEnergySimulation:
    """Supplied fixed-day MATD3 evidence. Read-only and never used as a device controller."""
    return svc.offline_energy_simulation(account_id, space_id)


@router.post("/plans/rest", response_model=Plan, operation_id="createRestPlan", tags=["plans"])
def create_rest_plan(body: CreateRestPlanRequest, svc: RestService = Svc) -> Plan:
    return svc.create_rest_plan(body.context, body.utterance, body.mode, body.wake_time or "07:00")


@router.post("/plans/{plan_id}/confirm", response_model=ConfirmPlanResponse, operation_id="confirmPlan", tags=["plans"])
def confirm_plan(plan_id: str, body: ConfirmPlanRequest, svc: RestService = Svc) -> ConfirmPlanResponse:
    return svc.confirm_plan(plan_id, body.context, body.plan_version)


@router.post(
    "/services/{service_id}/stop", response_model=StopServiceResponse, operation_id="stopService", tags=["services"]
)
def stop_service(service_id: str, body: StopServiceRequest, svc: RestService = Svc) -> StopServiceResponse:
    return svc.stop_service(service_id, body.context)


@router.post(
    "/services/{service_id}/clock/advance",
    response_model=AdvanceClockResponse,
    operation_id="advanceClock",
    tags=["services"],
)
def advance_clock(service_id: str, body: AdvanceClockRequest, svc: RestService = Svc) -> AdvanceClockResponse:
    """Simulated night clock (demo only). minutes=null jumps to the next pending step; each step runs once."""
    return svc.advance_clock(service_id, body.context, body.minutes)


@router.post(
    "/services/{service_id}/sleep",
    response_model=AdvanceClockResponse,
    operation_id="simulateSleep",
    tags=["services"],
)
def simulate_sleep(service_id: str, body: SimulateSleepRequest, svc: RestService = Svc) -> AdvanceClockResponse:
    """Explicit simulated sleep signal for the pitch demo; not a real sensor integration."""
    return svc.simulate_sleep(service_id, body.context)


@router.post(
    "/spaces/{space_id}/events", response_model=EventResult, operation_id="injectEvent", tags=["events"]
)
def inject_event(space_id: str, body: InjectEventRequest, svc: RestService = Svc) -> EventResult:
    """Simulated environment event. There is no real sensor; results are labelled source=simulated."""
    return svc.inject_event(space_id, body.context, body.type, body.room_temp_c)


@router.get(
    "/spaces/{space_id}/activity", response_model=ActivityResponse, operation_id="getActivity", tags=["activity"]
)
def get_activity(
    space_id: str,
    account_id: str = Query(alias="accountId"),
    limit: int = Query(default=50, ge=1, le=200),
    svc: RestService = Svc,
) -> ActivityResponse:
    return ActivityResponse(items=svc.activity(account_id, space_id, limit))


@router.post("/demo/reset", response_model=BootstrapResponse, operation_id="resetDemo", tags=["demo"])
def reset_demo(account_id: str = Query(alias="accountId"), svc: RestService = Svc) -> BootstrapResponse:
    return svc.reset(account_id)

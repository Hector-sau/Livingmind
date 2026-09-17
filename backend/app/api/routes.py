"""HTTP routes for the rest scenario. Handlers only translate HTTP <-> domain; logic lives in app/services."""

from fastapi import APIRouter, Depends, Query

from app.api.errors import ERROR_RESPONSES
from app.contracts import (
    ActivityResponse,
    BootstrapResponse,
    ConfirmPlanRequest,
    ConfirmPlanResponse,
    CreateRestPlanRequest,
    DeviceState,
    Plan,
    StopServiceRequest,
    StopServiceResponse,
)
from app.services.rest_service import RestService, get_rest_service

router = APIRouter(prefix="/api", responses=ERROR_RESPONSES)
Svc = Depends(get_rest_service)


@router.get("/bootstrap", response_model=BootstrapResponse, operation_id="getBootstrap", tags=["demo"])
def get_bootstrap(account_id: str = Query(alias="accountId"), svc: RestService = Svc) -> BootstrapResponse:
    return svc.bootstrap(account_id)


@router.get("/spaces/{space_id}/devices", response_model=DeviceState, operation_id="getDeviceState", tags=["devices"])
def get_device_state(space_id: str, account_id: str = Query(alias="accountId"), svc: RestService = Svc) -> DeviceState:
    return svc.device_state(account_id, space_id)


@router.post("/plans/rest", response_model=Plan, operation_id="createRestPlan", tags=["plans"])
def create_rest_plan(body: CreateRestPlanRequest, svc: RestService = Svc) -> Plan:
    return svc.create_rest_plan(body.context, body.utterance, body.mode)


@router.post("/plans/{plan_id}/confirm", response_model=ConfirmPlanResponse, operation_id="confirmPlan", tags=["plans"])
def confirm_plan(plan_id: str, body: ConfirmPlanRequest, svc: RestService = Svc) -> ConfirmPlanResponse:
    return svc.confirm_plan(plan_id, body.context, body.plan_version)


@router.post(
    "/services/{service_id}/stop", response_model=StopServiceResponse, operation_id="stopService", tags=["services"]
)
def stop_service(service_id: str, body: StopServiceRequest, svc: RestService = Svc) -> StopServiceResponse:
    return svc.stop_service(service_id, body.context)


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

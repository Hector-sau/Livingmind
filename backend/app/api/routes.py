"""HTTP routes for the rest scenario. Handlers only translate HTTP <-> domain; logic lives in app/services."""

from fastapi import APIRouter, Query

from app.api.errors import ERROR_RESPONSES, ApiError
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

router = APIRouter(prefix="/api", responses=ERROR_RESPONSES)


def _todo() -> ApiError:
    return ApiError("NOT_IMPLEMENTED", "接口已定义，业务逻辑在步骤 4 实现")


@router.get("/bootstrap", response_model=BootstrapResponse, operation_id="getBootstrap", tags=["demo"])
def get_bootstrap(account_id: str = Query(alias="accountId")) -> BootstrapResponse:
    raise _todo()


@router.get("/spaces/{space_id}/devices", response_model=DeviceState, operation_id="getDeviceState", tags=["devices"])
def get_device_state(space_id: str, account_id: str = Query(alias="accountId")) -> DeviceState:
    raise _todo()


@router.post("/plans/rest", response_model=Plan, operation_id="createRestPlan", tags=["plans"])
def create_rest_plan(body: CreateRestPlanRequest) -> Plan:
    raise _todo()


@router.post("/plans/{plan_id}/confirm", response_model=ConfirmPlanResponse, operation_id="confirmPlan", tags=["plans"])
def confirm_plan(plan_id: str, body: ConfirmPlanRequest) -> ConfirmPlanResponse:
    raise _todo()


@router.post(
    "/services/{service_id}/stop", response_model=StopServiceResponse, operation_id="stopService", tags=["services"]
)
def stop_service(service_id: str, body: StopServiceRequest) -> StopServiceResponse:
    raise _todo()


@router.get(
    "/spaces/{space_id}/activity", response_model=ActivityResponse, operation_id="getActivity", tags=["activity"]
)
def get_activity(
    space_id: str,
    account_id: str = Query(alias="accountId"),
    limit: int = Query(default=50, ge=1, le=200),
) -> ActivityResponse:
    raise _todo()


@router.post("/demo/reset", response_model=BootstrapResponse, operation_id="resetDemo", tags=["demo"])
def reset_demo(account_id: str = Query(alias="accountId")) -> BootstrapResponse:
    raise _todo()

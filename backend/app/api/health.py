from fastapi import APIRouter
from pydantic import BaseModel

from app.config import APP_VERSION

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    version: str


@router.get("/health", response_model=HealthResponse, operation_id="getHealth")
def health() -> HealthResponse:
    return HealthResponse(status="ok", version=APP_VERSION)

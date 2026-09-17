"""Unified error format: every non-2xx response is {"error": {"code", "message", "details"}}."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.contracts import ErrorBody, ErrorCode, ErrorResponse

STATUS_BY_CODE: dict[str, int] = {
    "VALIDATION_ERROR": 422,
    "NOT_FOUND": 404,
    "FORBIDDEN_CONTEXT": 403,
    "PLAN_EXPIRED": 409,
    "PLAN_INVALIDATED": 409,
    "PLAN_VERSION_MISMATCH": 409,
    "SERVICE_ALREADY_ACTIVE": 409,
    "SERVICE_NOT_ACTIVE": 409,
    "NOT_IMPLEMENTED": 501,
    "INTERNAL_ERROR": 500,
}


class ApiError(Exception):
    def __init__(self, code: ErrorCode, message: str, details: Optional[dict[str, Any]] = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details


def _response(code: ErrorCode, message: str, details: Optional[dict[str, Any]] = None) -> JSONResponse:
    body = ErrorResponse(error=ErrorBody(code=code, message=message, details=details))
    return JSONResponse(status_code=STATUS_BY_CODE[code], content=body.model_dump(mode="json", by_alias=True))


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
        return _response(exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [{"loc": list(e.get("loc", [])), "msg": e.get("msg", "")} for e in exc.errors()]
        return _response("VALIDATION_ERROR", "请求参数不合法", {"errors": errors})


# Shared OpenAPI declaration so generated TS clients know the error shape.
ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    status: {"model": ErrorResponse} for status in (403, 404, 409, 422, 501)
}

import json
import logging
import re
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api import health, routes
from app.api.errors import install_error_handlers
from app.config import APP_NAME, APP_VERSION, CORS_ORIGINS
from app.observability.context import reset_request_id, set_request_id

_REQUEST_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_http_log = logging.getLogger("livingmind.http")
_http_log.setLevel(logging.INFO)
_http_log.propagate = False
if not _http_log.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(message)s"))
    _http_log.addHandler(_handler)


def create_app() -> FastAPI:
    # One schema per model (no -Input/-Output split) keeps generated TS names stable.
    app = FastAPI(title=APP_NAME, version=APP_VERSION, separate_input_output_schemas=False)

    @app.middleware("http")
    async def request_trace(request: Request, call_next):
        supplied = request.headers.get("x-request-id", "")
        request_id = supplied if _REQUEST_ID.fullmatch(supplied) else uuid.uuid4().hex
        token = set_request_id(request_id)
        started = time.monotonic()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            _http_log.info(json.dumps({
                "requestId": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": status,
                "durationMs": int((time.monotonic() - started) * 1000),
            }, ensure_ascii=False))
            reset_request_id(token)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    install_error_handlers(app)
    app.include_router(health.router)
    app.include_router(routes.router)
    return app


app = create_app()

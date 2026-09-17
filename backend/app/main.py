from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import health, routes
from app.api.errors import install_error_handlers
from app.config import APP_NAME, APP_VERSION, CORS_ORIGINS


def create_app() -> FastAPI:
    # One schema per model (no -Input/-Output split) keeps generated TS names stable.
    app = FastAPI(title=APP_NAME, version=APP_VERSION, separate_input_output_schemas=False)
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

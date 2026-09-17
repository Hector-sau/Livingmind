"""Runtime settings read from environment variables (secrets live only here, never in the app)."""

import os


def _csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


APP_NAME = "LivingMind API"
APP_VERSION = "0.1.0"
# Comma-separated origins allowed for the web preview. Native apps do not need CORS.
CORS_ORIGINS = _csv(os.getenv("LIVINGMIND_CORS_ORIGINS", "http://localhost:8081,http://127.0.0.1:8081"))

"""Runtime settings read from environment variables (secrets live only here, never in the app)."""

import os


def _csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


APP_NAME = "LivingMind API"
APP_VERSION = "0.1.0"
# Comma-separated origins allowed for the web preview. Native apps do not need CORS.
CORS_ORIGINS = _csv(os.getenv("LIVINGMIND_CORS_ORIGINS", "http://localhost:8081,http://127.0.0.1:8081"))


# ---- persistence (T2) ----
# Empty = the demo runs fully in memory (default). Set to a PostgreSQL URL to persist
# business facts, e.g. postgresql+psycopg://livingmind:...@127.0.0.1:5432/livingmind
DATABASE_URL = os.getenv("LIVINGMIND_DATABASE_URL", "").strip()


# ---- planner / Experience Agent ----
# "rule": never call a model. "model": call the configured provider, fall back to rules on failure.
PLANNER_DEFAULT_MODE = os.getenv("LIVINGMIND_PLANNER_MODE", "rule")
MODEL_PROVIDER = os.getenv("LIVINGMIND_MODEL_PROVIDER", "deepseek")
MODEL_TIMEOUT_S = float(os.getenv("LIVINGMIND_MODEL_TIMEOUT_S", "6"))
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-flash")

# ---- environment events (step 6) ----
EVENT_COOLDOWN_S = float(os.getenv("LIVINGMIND_EVENT_COOLDOWN_S", "30"))
EVENT_MAX_ADJUSTMENTS = int(os.getenv("LIVINGMIND_EVENT_MAX_ADJUSTMENTS", "3"))

# ---- energy (step 8) ----
# Local hour override for the time-of-use tariff, so demos and tests are deterministic.
_demo_hour = os.getenv("LIVINGMIND_DEMO_LOCAL_HOUR", "").strip()
DEMO_LOCAL_HOUR = int(_demo_hour) if _demo_hour else None
LOCAL_UTC_OFFSET_HOURS = int(os.getenv("LIVINGMIND_LOCAL_UTC_OFFSET", "8"))

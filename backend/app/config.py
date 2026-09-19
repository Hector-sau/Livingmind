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


# ---- cache / coordination (T4) ----
# Empty = no Redis. Redis only shortens races and speeds up checks; PostgreSQL stays
# authoritative and every cache call degrades silently when Redis is unreachable.
REDIS_URL = os.getenv("LIVINGMIND_REDIS_URL", "").strip()


# ---- orchestration (T3) ----
# "legacy": the sequential main Agent (default). "langgraph": the same stages run as a
# LangGraph StateGraph with checkpoints. Both must produce equivalent plans.
ORCHESTRATOR = os.getenv("LIVINGMIND_ORCHESTRATOR", "legacy").strip() or "legacy"


# ---- planner / Experience Agent ----
# "rule": never call a model. "model": call the configured provider, fall back to rules on failure.
PLANNER_DEFAULT_MODE = os.getenv("LIVINGMIND_PLANNER_MODE", "rule")
MODEL_PROVIDER = os.getenv("LIVINGMIND_MODEL_PROVIDER", "deepseek")
MODEL_TIMEOUT_S = float(os.getenv("LIVINGMIND_MODEL_TIMEOUT_S", "6"))
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
# Measured over 48 real calls each (docs/evidence/model-latency-*.json): deepseek-chat returned
# a usable plan every time, p95 1513 ms, slowest 2103 ms. deepseek-flash reasons before answering
# and its tail is much longer -- 13% of calls over 2.5 s, two past the 6 s budget. This task turns
# one sentence into three bounded numbers; it does not need long reasoning, so it does not pay for it.
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
# deepseek-flash writes reasoning before its answer, and that reasoning is charged against the
# same budget. A measured run (docs/evidence/model-latency.json) produced 1280-1387 characters
# of reasoning on the harder utterances, which spent a 400-token budget before a single character
# of the answer was written. 2000 leaves room for the reasoning and the JSON object after it.
MODEL_MAX_TOKENS = int(os.getenv("LIVINGMIND_MODEL_MAX_TOKENS", "2000"))

# ---- environment events (step 6) ----
EVENT_COOLDOWN_S = float(os.getenv("LIVINGMIND_EVENT_COOLDOWN_S", "30"))
# How long a direct device control can be undone. Short on purpose: long enough to
# read the bar, short enough that the device state is not left ambiguous.
UNDO_WINDOW_S = float(os.getenv("LIVINGMIND_UNDO_WINDOW_S", "5"))
EVENT_MAX_ADJUSTMENTS = int(os.getenv("LIVINGMIND_EVENT_MAX_ADJUSTMENTS", "3"))

# ---- energy (step 8) ----
# Local hour override for the time-of-use tariff, so demos and tests are deterministic.
_demo_hour = os.getenv("LIVINGMIND_DEMO_LOCAL_HOUR", "").strip()
DEMO_LOCAL_HOUR = int(_demo_hour) if _demo_hour else None
LOCAL_UTC_OFFSET_HOURS = int(os.getenv("LIVINGMIND_LOCAL_UTC_OFFSET", "8"))

"""One real Experience Agent call against the configured provider. Run this on a machine that
has the key, to verify step 5 for real and to record the actual latency.

    cd backend && set -a && source .env && set +a && .venv/bin/python scripts/try_model.py "我想休息，有点热"

Prints the structured output and latency. Never prints the key.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import config  # noqa: E402
from app.agents.experience import ExperienceAgent, ExperienceError  # noqa: E402
from app.clock import utc_now  # noqa: E402
from app.demo import seed  # noqa: E402
from app.contracts import DeviceState  # noqa: E402
from app.services.planner import provider_from_config  # noqa: E402


def main() -> int:
    utterance = sys.argv[1] if len(sys.argv) > 1 else "我想休息"
    provider = provider_from_config()
    if provider is None:
        print("模型未配置：请在 backend/.env 里填写 DEEPSEEK_API_KEY，并用 `set -a && source .env` 加载。")
        return 2
    print(f"provider={provider.name} model={provider.model} timeout={config.MODEL_TIMEOUT_S}s")
    person = seed.PERSONS[0]
    state = DeviceState(space_id=seed.DEFAULT_SPACE_ID, **seed.INITIAL_DEVICE_STATE, source="virtual_device", version=0, updated_at=utc_now())
    agent = ExperienceAgent(provider, config.MODEL_TIMEOUT_S)
    try:
        result = agent.plan(person, state, utterance)
    except ExperienceError as exc:
        print(f"FAILED ({exc.kind}) after {exc.latency_ms} ms: {exc.message}")
        return 1
    print(f"OK in {result.latency_ms} ms")
    print(result.output.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

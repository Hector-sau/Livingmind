"""Read-only access to supplied offline Home Energy simulation evidence.

This module deliberately does not import torch, gym, or the research implementation.
It serves the supplied fixed-day data for transparent in-app presentation only.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.contracts import OfflineEnergySimulation


ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "simulation" / "home-energy" / "data"


@lru_cache(maxsize=1)
def offline_energy_simulation() -> OfflineEnergySimulation:
    comparison = json.loads((DATA / "provided-day-comparison.json").read_text(encoding="utf-8"))
    inputs = json.loads((DATA / "fixed-day-inputs.json").read_text(encoding="utf-8"))
    profile = [
        {
            "hour": hour,
            "pv_kw": inputs["pvKw"][hour],
            "wind_kw": inputs["windKw"][hour],
            "base_load_kw": inputs["baseLoadKw"][hour],
            "buy_price_usd_per_kwh": inputs["buyPriceUsdPerKwh"][hour],
            "outdoor_temp_f": inputs["outdoorTempF"][hour],
        }
        for hour in range(24)
    ]
    return OfflineEnergySimulation(
        source=comparison["source"],
        scenario=comparison["scenario"],
        controller=comparison["controller"],
        agent_count=comparison["agentCount"],
        resolution=comparison["resolution"],
        metrics=comparison["metrics"],
        assets=comparison["assets"],
        profile=profile,
        limits=comparison["limits"],
    )


from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from app.contracts import EnergyAdvice, EnergyMode, PowerTier, RestPreference

COMFORT_HALF_BAND_C = 1.0  # comfort band = experience target ± 1 °C
ECO_STEP_C = 0.5  # how far eco mode may raise the set point at peak tariff


def comfort_band(target: RestPreference) -> tuple[float, float]:
    t = target.ac_target_temp_c
    return max(16.0, t - COMFORT_HALF_BAND_C), min(30.0, t + COMFORT_HALF_BAND_C)


def estimate_load_kw(ac_target_c: float, light_brightness: int, outdoor_c: float) -> float:
    """Very rough rule estimate for display only (cooling scales with the indoor/outdoor gap)."""
    cooling = max(0.0, outdoor_c - ac_target_c) * 0.12
    lighting = light_brightness / 100 * 0.03
    return round(cooling + lighting, 2)


def power_tier(kw: float) -> PowerTier:
    if kw < 0.5:
        return "low"
    if kw < 0.9:
        return "medium"
    return "high"


TIER_LABEL = {"low": "低", "medium": "中", "high": "高"}


class EnergyIntelligence:
    def __init__(self, outdoor_temp_c: float, peak_hours: range, utc_offset_hours: int, demo_local_hour: Optional[int]):
        self._outdoor = outdoor_temp_c
        self._peak = peak_hours
        self._offset = utc_offset_hours
        self._demo_hour = demo_local_hour

    def local_hour(self, now: datetime) -> int:
        if self._demo_hour is not None:
            return self._demo_hour
        return (now + timedelta(hours=self._offset)).hour

    def advise(self, target: RestPreference, mode: EnergyMode, now: datetime) -> EnergyAdvice:
        low, high = comfort_band(target)
        requested = target.ac_target_temp_c
        tariff = "peak" if self.local_hour(now) in self._peak else "offpeak"
        cooling = self._outdoor > requested
        recommended = requested
        if cooling and tariff == "peak":
            recommended = min(requested + ECO_STEP_C, high)
            why = (
                f"室外约 {self._outdoor:g}°C、当前为高峰电价时段，"
                f"在舒适范围 {low:g}–{high:g}°C 内把空调设定提高 {recommended - requested:g}°C 可降低制冷负荷"
            )
        elif cooling:
            why = "非高峰时段，保持体验目标温度"
        else:
            why = "室外不高于设定温度，不需要制冷，保持体验目标"
        applied = mode == "eco" and recommended != requested
        final = recommended if applied else requested
        before = estimate_load_kw(requested, target.light_brightness, self._outdoor)
        after = estimate_load_kw(final, target.light_brightness, self._outdoor)
        if recommended != requested and not applied:
            why += "；当前为“舒适优先”，只给建议不改设定"
        return EnergyAdvice(
            mode=mode,
            tariff=tariff,
            outdoor_temp_c=self._outdoor,
            comfort_min_c=low,
            comfort_max_c=high,
            requested_ac_c=requested,
            recommended_ac_c=recommended,
            applied=applied,
            load_kw_before=before,
            load_kw_after=after,
            tier_before=power_tier(before),
            tier_after=power_tier(after),
            reason=why,
            source="rule",
        )

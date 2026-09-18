"""Every Redis key in one place, with the TTL that owns it."""

from __future__ import annotations

PREFIX = "livingmind"

# One writer per space while devices are being driven (confirm, night step, adjustment).
def space_executor_lock(space_id: str) -> str:
    return f"{PREFIX}:lock:space:{space_id}:executor"


# Fast pre-check for the 30 s event cooldown; the service row stays authoritative.
def event_cooldown(service_id: str) -> str:
    return f"{PREFIX}:cooldown:service:{service_id}:room_temp"


EXECUTOR_LOCK_TTL_S = 30

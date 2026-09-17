"""Stateful virtual devices for one space. Simulated hardware: never describe as a real integration."""

from __future__ import annotations

import threading
from dataclasses import dataclass

from app.clock import Clock
from app.contracts import Capability, DeviceCommand, DeviceState, DeviceType

CAPABILITIES = [
    Capability(device="light", command="set_brightness", min=0, max=100, integer=True),
    Capability(device="ac", command="set_target_temperature", min=16, max=30, integer=False),
    Capability(device="curtain", command="set_open_percent", min=0, max=100, integer=True),
]


@dataclass
class _State:
    light_brightness: int
    ac_target_temp_c: float
    curtain_open_percent: int
    version: int


class VirtualDeviceAdapter:
    """Keeps real in-memory state; writes change it and reads return it."""

    def __init__(self, space_id: str, initial: dict, clock: Clock):
        self.space_id = space_id
        self._initial = dict(initial)
        self._clock = clock
        self._state = _State(version=0, **self._initial)
        self._updated_at = clock()
        # Device-level lock: state reads/writes are atomic even when the service lock is not held.
        self._lock = threading.Lock()

    def list_capabilities(self) -> list[Capability]:
        return list(CAPABILITIES)

    def reset(self) -> None:
        with self._lock:
            self._state = _State(version=0, **self._initial)
            self._updated_at = self._clock()

    def read_state(self) -> DeviceState:
        with self._lock:
            return self._snapshot()

    def _snapshot(self) -> DeviceState:
        s = self._state
        return DeviceState(
            space_id=self.space_id,
            light_brightness=s.light_brightness,
            ac_target_temp_c=s.ac_target_temp_c,
            curtain_open_percent=s.curtain_open_percent,
            source="virtual_device",
            version=s.version,
            updated_at=self._updated_at,
        )

    def write(self, device: DeviceType, command: DeviceCommand, value: float) -> None:
        """Low-level write. Only the executor should call this. May be slow for real hardware."""
        self._before_write(device, command, value)
        with self._lock:
            if (device, command) == ("light", "set_brightness"):
                self._state.light_brightness = int(value)
            elif (device, command) == ("ac", "set_target_temperature"):
                self._state.ac_target_temp_c = float(value)
            elif (device, command) == ("curtain", "set_open_percent"):
                self._state.curtain_open_percent = int(value)
            else:  # pragma: no cover - executor whitelist prevents this
                raise ValueError(f"unsupported command {device}.{command}")
            self._state.version += 1
            self._updated_at = self._clock()

    def _before_write(self, device: DeviceType, command: DeviceCommand, value: float) -> None:
        """Hook for subclasses/tests to simulate device latency. No-op for the instant virtual device."""

    def read_value(self, device: DeviceType) -> float:
        with self._lock:
            s = self._state
            return {"light": s.light_brightness, "ac": s.ac_target_temp_c, "curtain": s.curtain_open_percent}[device]

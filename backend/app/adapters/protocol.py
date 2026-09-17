"""Stable seam for future SpaceMind/base-device integrations.

The demo injects ``VirtualDeviceAdapter`` here. A real vendor or base adapter must
implement this small protocol and remains constrained by the Harness executor.
"""

from __future__ import annotations

from typing import Protocol

from app.contracts import Capability, DeviceCommand, DeviceState, DeviceType


class DeviceAdapter(Protocol):
    space_id: str

    def list_capabilities(self) -> list[Capability]: ...

    def read_state(self) -> DeviceState: ...

    def write(self, device: DeviceType, command: DeviceCommand, value: float) -> None: ...

    def read_value(self, device: DeviceType) -> float: ...

    def reset(self) -> None: ...

"""Stable seam for future SpaceMind/base-device integrations.

The demo injects ``VirtualDeviceAdapter`` here. A real vendor or base adapter must
implement this small protocol and remains constrained by the Harness executor.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Optional, Protocol, runtime_checkable

from app.contracts import Capability, DeviceCommand, DeviceState, DeviceType


@runtime_checkable
class DeviceAdapter(Protocol):
    space_id: str

    def list_capabilities(self) -> list[Capability]: ...

    def read_state(self) -> DeviceState: ...

    def write(self, device: DeviceType, command: DeviceCommand, value: float) -> None: ...

    def read_value(self, device: DeviceType) -> float: ...

    def reset(self) -> None: ...


CommandStatus = Literal["accepted", "completed", "rejected", "unknown"]
DeviceErrorKind = Literal["offline", "timeout", "unauthorized", "unsupported", "rejected", "unknown"]


@dataclass(frozen=True)
class DeviceDescriptor:
    device_id: str
    space_id: str
    device_type: DeviceType
    capabilities: tuple[Capability, ...]


@dataclass(frozen=True)
class DeviceCommandRequest:
    """Command envelope for a real base/vendor gateway."""

    action_id: str
    service_id: Optional[str]
    service_epoch: int
    device_id: str
    device_type: DeviceType
    command: DeviceCommand
    value: float
    requested_at: datetime


@dataclass(frozen=True)
class DeviceCommandReceipt:
    action_id: str
    status: CommandStatus
    observed_value: Optional[float]
    observed_at: Optional[datetime]
    error_kind: Optional[DeviceErrorKind] = None
    detail: Optional[str] = None


@runtime_checkable
class DeviceGateway(Protocol):
    """Reserved V2 seam: identity, idempotency key, epoch and typed acknowledgements."""

    def list_devices(self, space_id: str) -> list[DeviceDescriptor]: ...

    def submit(self, request: DeviceCommandRequest) -> DeviceCommandReceipt: ...

    def query(self, action_id: str) -> Optional[DeviceCommandReceipt]: ...

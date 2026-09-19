"""DeviceGateway V2 backed by the current virtual/legacy adapter.

The wrapper makes idempotency and fencing executable before a real SpaceMind or vendor
gateway is available. A repeated action id returns its original receipt. An epoch below
the space fence is rejected before touching the adapter.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone

from app.adapters.protocol import (
    DeviceAdapter,
    DeviceCommandReceipt,
    DeviceCommandRequest,
    DeviceDescriptor,
)


class AdapterDeviceGateway:
    def __init__(self, adapter: DeviceAdapter):
        self.adapter = adapter
        self._receipts: dict[str, DeviceCommandReceipt] = {}
        self._requests: dict[str, tuple] = {}
        self._fences: dict[str, int] = {}
        self._lock = threading.RLock()

    def list_devices(self, space_id: str) -> list[DeviceDescriptor]:
        if space_id != self.adapter.space_id:
            return []
        grouped = {}
        for capability in self.adapter.list_capabilities():
            grouped.setdefault(capability.device, []).append(capability)
        return [
            DeviceDescriptor(
                device_id=f"{space_id}:{device_type}",
                space_id=space_id,
                device_type=device_type,
                capabilities=tuple(capabilities),
            )
            for device_type, capabilities in grouped.items()
        ]

    def advance_fence(self, space_id: str, service_epoch: int) -> None:
        with self._lock:
            self._fences[space_id] = max(service_epoch, self._fences.get(space_id, 0))

    def submit(self, request: DeviceCommandRequest) -> DeviceCommandReceipt:
        fingerprint = (
            request.service_id,
            request.service_epoch,
            request.device_id,
            request.device_type,
            request.command,
            float(request.value),
        )
        with self._lock:
            prior = self._receipts.get(request.action_id)
            if prior is not None:
                if self._requests.get(request.action_id) != fingerprint:
                    return DeviceCommandReceipt(
                        action_id=request.action_id,
                        status="rejected",
                        observed_value=None,
                        observed_at=None,
                        error_kind="rejected",
                        detail="actionId 已被另一条设备命令使用",
                    )
                return prior
            fence = self._fences.get(self.adapter.space_id, 0)
            if request.service_epoch < fence:
                receipt = DeviceCommandReceipt(
                    action_id=request.action_id,
                    status="rejected",
                    observed_value=None,
                    observed_at=None,
                    error_kind="rejected",
                    detail=f"stale service epoch {request.service_epoch}; current fence is {fence}",
                )
                self._receipts[request.action_id] = receipt
                return receipt
            self._fences[self.adapter.space_id] = max(fence, request.service_epoch)
            # Reserve the id before leaving the lock. A concurrent retry sees accepted
            # instead of executing the physical write a second time.
            self._requests[request.action_id] = fingerprint
            self._receipts[request.action_id] = DeviceCommandReceipt(
                action_id=request.action_id,
                status="accepted",
                observed_value=None,
                observed_at=None,
            )

        try:
            self.adapter.write(request.device_type, request.command, request.value)
        except Exception as exc:
            receipt = DeviceCommandReceipt(
                action_id=request.action_id,
                status="failed",
                observed_value=None,
                observed_at=None,
                error_kind="unknown",
                detail=str(exc),
            )
        else:
            try:
                observed = self.adapter.read_value(request.device_type)
            except Exception as exc:
                receipt = DeviceCommandReceipt(
                    action_id=request.action_id,
                    status="failed",
                    observed_value=None,
                    observed_at=None,
                    error_kind="unknown",
                    detail=f"设备写入后回读失败：{exc}",
                )
            else:
                receipt = DeviceCommandReceipt(
                    action_id=request.action_id,
                    status="completed",
                    observed_value=observed,
                    observed_at=datetime.now(timezone.utc),
                )
        with self._lock:
            self._receipts[request.action_id] = receipt
            return receipt

    def query(self, action_id: str) -> DeviceCommandReceipt | None:
        with self._lock:
            return self._receipts.get(action_id)

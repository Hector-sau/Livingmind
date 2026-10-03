"""Bounded HTTP transport. No retries: a timeout does not imply no device write."""
from dataclasses import asdict

import httpx
from fastapi.encoders import jsonable_encoder
from pydantic import TypeAdapter, ValidationError

from app.adapters.protocol import DeviceCommandReceipt, DeviceDescriptor
from app.contracts import Capability, DeviceState


class HttpDeviceAdapter:
    def __init__(self, space_id, base_url, token, epoch, timeout_s=3):
        if not token:
            raise RuntimeError("LIVINGMIND_GATEWAY_TOKEN is required")
        self.space_id, self.epoch = space_id, epoch
        self.client = httpx.Client(base_url=base_url, headers={"Authorization": f"Bearer {token}"}, timeout=timeout_s)

    def request(self, method, path, **kwargs):
        try:
            response = self.client.request(method, path, **kwargs)
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise OSError(f"gateway transport failed: {type(exc).__name__}") from exc

    def list_capabilities(self):
        return [Capability.model_validate(x) for x in self.request("GET", f"/spaces/{self.space_id}/capabilities")]

    def read_state(self):
        return DeviceState.model_validate(self.request("GET", f"/spaces/{self.space_id}/state"))

    def read_value(self, device):
        return getattr(self.read_state(), {"light": "light_brightness", "ac": "ac_target_temp_c", "curtain": "curtain_open_percent"}[device])

    def write(self, *args):
        raise RuntimeError("Remote writes require an actionId and must use DeviceGateway.submit")

    def reset(self):
        result = self.request("POST", f"/spaces/{self.space_id}/reset", json={"epoch": self.epoch(self.space_id)})
        if not result.get("reset"):
            raise OSError("gateway rejected a stale reset; device state was not reset")

    def close(self):
        self.client.close()


class HttpDeviceGateway:
    def __init__(self, adapter):
        self.adapter = adapter

    def list_devices(self, space_id):
        if space_id != self.adapter.space_id:
            return []
        grouped = {}
        for cap in self.adapter.list_capabilities():
            grouped.setdefault(cap.device, []).append(cap)
        return [DeviceDescriptor(f"{space_id}:{kind}", space_id, kind, tuple(caps)) for kind, caps in grouped.items()]

    def advance_fence(self, space_id, service_epoch):
        self.adapter.request("POST", f"/spaces/{space_id}/fence", json={"epoch": service_epoch})

    @staticmethod
    def receipt(body):
        if body is None:
            return None
        try:
            return TypeAdapter(DeviceCommandReceipt).validate_python(body)
        except (TypeError, ValueError, ValidationError) as exc:
            raise OSError("invalid gateway receipt") from exc

    def submit(self, request):
        receipt = self.receipt(self.adapter.request("POST", "/commands", json=jsonable_encoder(asdict(request))))
        if receipt is None:
            raise OSError("gateway returned no command receipt")
        return receipt

    def query(self, action_id):
        return self.receipt(self.adapter.request("GET", f"/commands/{action_id}"))

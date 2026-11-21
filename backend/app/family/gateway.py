"""Map household actions onto model-specific MIoT properties. The default transport is local."""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
from math import isfinite
from threading import RLock
from typing import Protocol

ROOMS = [
    {"id": "living", "name": "客厅"},
    {"id": "study", "name": "书房"},
    {"id": "bedroom", "name": "卧室"},
]


def fixture(device_id, name, room, service, prop, unit, initial, bounds, *, did=None, siid=2, piid=2):
    return {
        "id": device_id, "name": name, "roomId": room, "value": initial, "unit": unit,
        "mode": "online", "source": "simulated", "lastObserved": initial,
        "capability": {
            "service": service, "property": prop, "did": "sim-" + device_id if did is None else did,
            "siid": siid, "piid": piid,
            "access": ["read", "write", "notify"], "valueRange": bounds,
        },
    }


DEVICES = [
    fixture("living-light", "客厅灯", "living", "light", "brightness", "%", 0, [0, 100, 1]),
    fixture("desk-light", "书桌灯", "study", "light", "brightness", "%", 20, [0, 100, 1]),
    fixture("bed-light", "床头灯", "bedroom", "light", "brightness", "%", 36, [0, 100, 1]),
    fixture("living-ac", "客厅空调", "living", "air-conditioner", "target-temperature", "°C", 27, [16, 30, 1]),
    fixture("living-curtain", "客厅窗帘", "living", "curtain", "target-position", "%", 80, [0, 100, 1]),
    fixture("living-speaker", "客厅音箱", "living", "speaker", "volume", "%", 0, [0, 100, 1]),
    fixture("study-fan", "书房循环扇", "study", "fan", "fan-level", "档", 0, [0, 3, 1]),
    fixture("bed-curtain", "卧室窗帘", "bedroom", "curtain", "target-position", "%", 60, [0, 100, 1]),
]


class FamilyDeviceGateway(Protocol):
    """Transport seam. A real bridge must normalize units and await a fresh readback."""

    def snapshot(self) -> list: ...
    def submit(self, action_id: str, device_id: str, value: int | float) -> dict: ...


class MiotPropertyTransport(Protocol):
    """Return one addressed property reply per call. A read must be a fresh observation."""

    def write_property(self, packet: dict) -> dict | None: ...
    def read_property(self, address: dict) -> dict | None: ...


def property_packet(device, value=None):
    cap = device["capability"]
    # Older exported virtual snapshots did not include a DID.
    did = cap.get("did", "sim-" + device["id"])
    packet = {"did": did, "siid": cap["siid"], "piid": cap["piid"]}
    if value is not None:
        packet["value"] = value
    return packet


def _address_matches(reply, address):
    return isinstance(reply, dict) and all(
        type(reply.get(key)) is type(value) and reply[key] == value for key, value in address.items()
    )


def _write_accepted(reply, address):
    return (_address_matches(reply, address) and type(reply.get("code")) is int
            and reply["code"] in (0, 1))


def matches_value_range(value, bounds):
    """Check that a numeric value lies on a MIoT property's decimal step grid."""
    low, high, step = bounds
    if type(value) not in (int, float) or not low <= value <= high:
        return False
    # MIoT steps can be decimal, e.g. 0.1 °C. Preserve the protocol's decimal grid.
    return (Decimal(str(value)) - Decimal(str(low))) % Decimal(str(step)) == 0


def decode_observation(device, write_reply, read_reply, expected):
    """A successful set response carries no proof of the observed property value."""
    address = property_packet(device)
    if not _write_accepted(write_reply, address) or not _address_matches(read_reply, address):
        return "unknown", None
    if type(read_reply.get("code")) is not int or read_reply["code"] != 0:
        return "unknown", None
    observed = read_reply.get("value")
    if not matches_value_range(observed, device["capability"]["valueRange"]):
        return "unknown", None
    return ("confirmed" if observed == expected else "mismatch"), observed


def _single_reply(reply):
    """Keep only scalar protocol fields suitable for the public device receipt."""
    if not isinstance(reply, dict):
        return None
    return {key: val for key, val in reply.items() if key in {"did", "siid", "piid", "code", "value"}
            and (type(val) in (str, int) or type(val) is float and isfinite(val))}


class MiotPropertyGateway:
    """One process-local receipt ledger per household. Transport lifetime belongs to the caller."""

    def __init__(self, devices, transport: MiotPropertyTransport, *, source="injected-transport"):
        self.transport = transport
        self.source = source
        self.lock = RLock()
        self.devices = {}
        addresses = set()
        for descriptor in devices:
            device = deepcopy(descriptor)
            cap = device["capability"]
            if not isinstance(cap.get("did"), str) or not cap["did"].strip():
                raise ValueError("Each mapped property needs an explicit did")
            if any(type(cap.get(key)) is not int or cap[key] < 1 for key in ("siid", "piid")):
                raise ValueError("siid and piid must be positive integers")
            low, high, step = cap["valueRange"]
            if (not all(type(v) in (int, float) and isfinite(v) for v in (low, high, step))
                    or low > high or step <= 0):
                raise ValueError("Expected a finite valueRange [minimum, maximum, positive step]")
            address = (cap["did"], cap["siid"], cap["piid"])
            if device["id"] in self.devices or address in addresses:
                raise ValueError("Duplicate logical ID or MIoT property address")
            addresses.add(address)
            device["source"] = source
            self.devices[device["id"]] = device
        self.receipts = {}

    def snapshot(self):
        with self.lock:
            return deepcopy(list(self.devices.values()))

    def submit(self, action_id, device_id, value):
        """Remember uncertain results too. A repeated action never repeats a write."""
        with self.lock:
            return self._submit_locked(action_id, device_id, value)

    def _submit_locked(self, action_id, device_id, value):
        if action_id in self.receipts:
            prior = self.receipts[action_id]
            if (prior["deviceId"], prior["requested"]) != (device_id, value):
                raise ValueError("action id reused for a different command")
            return deepcopy(prior)
        device = self.devices[device_id]
        cap = device["capability"]
        observed = None
        packet = property_packet(device, value)
        write_reply = read_reply = None
        if "write" not in cap["access"] or not matches_value_range(value, cap["valueRange"]):
            status = "rejected"
        elif device["mode"] == "offline":
            status = "offline"
        else:
            address = property_packet(device)
            try:
                write_reply = _single_reply(self.transport.write_property(dict(packet)))
                if _write_accepted(write_reply, address) and "read" in cap["access"]:
                    read_reply = _single_reply(self.transport.read_property(dict(address)))
            except Exception:
                # An adapter may raise after a write has taken effect. Never replay it.
                pass
            if (_address_matches(write_reply, address) and type(write_reply.get("code")) is int
                    and write_reply["code"] < 0):
                status = "rejected"
            else:
                status, observed = decode_observation(device, write_reply, read_reply, value)
                if observed is None:
                    device["mode"] = "unknown"
                else:
                    device.update(value=observed, lastObserved=observed, mode="online")
        result = {"actionId": action_id, "deviceId": device_id, "requested": value,
                  "status": status, "observed": observed, "source": self.source,
                  "propertyRequest": packet, "writeReply": write_reply, "readReply": read_reply}
        self.receipts[action_id] = result
        return deepcopy(result)


class _VirtualProperties:
    def __init__(self):
        self.values = {}
        self.unobserved = set()

    @staticmethod
    def key(address):
        return address["did"], address["siid"], address["piid"]

    def write_property(self, packet):
        address = {key: packet[key] for key in ("did", "siid", "piid")}
        self.values[self.key(address)] = packet["value"]
        return {**address, "code": 0}

    def read_property(self, address):
        key = self.key(address)
        if key in self.unobserved:
            return None
        return {**address, "value": self.values[key], "code": 0}


class VirtualFamilyGateway(MiotPropertyGateway):
    """Offline default including the simulator's connection fault controls."""

    def __init__(self, devices=DEVICES):
        super().__init__(devices, _VirtualProperties(), source="simulated")
        for device in self.devices.values():
            key = self.transport.key(property_packet(device))
            self.transport.values[key] = device["value"]
            self.set_mode(device["id"], device["mode"])

    def set_mode(self, device_id, mode):
        if mode not in ("online", "offline", "unknown"):
            raise ValueError("Unknown simulated connection mode")
        with self.lock:
            device = self.devices[device_id]
            address = property_packet(device)
            key = self.transport.key(address)
            if mode == "unknown":
                self.transport.unobserved.add(key)
            else:
                self.transport.unobserved.discard(key)
            device["mode"] = mode
            if mode == "online":
                observed = self.transport.read_property(address)["value"]
                device.update(value=observed, lastObserved=observed)

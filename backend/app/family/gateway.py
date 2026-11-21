"""MIoT-style simulation fixtures. Numeric IDs belong to these virtual models only."""
from __future__ import annotations

from copy import deepcopy
from typing import Protocol

ROOMS = [
    {"id": "living", "name": "客厅"},
    {"id": "study", "name": "书房"},
    {"id": "bedroom", "name": "卧室"},
]


def fixture(device_id, name, room, service, prop, unit, initial, bounds):
    return {
        "id": device_id, "name": name, "roomId": room, "value": initial, "unit": unit,
        "mode": "online", "source": "simulated", "lastObserved": initial,
        "capability": {
            "service": service, "property": prop, "siid": 2, "piid": 2,
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
    def submit(self, action_id: str, device_id: str, value: int) -> dict: ...


def property_packet(device, value=None):
    cap = device["capability"]
    packet = {"did": "sim-" + device["id"], "siid": cap["siid"], "piid": cap["piid"]}
    if value is not None:
        packet["value"] = value
    return packet


def decode_observation(device, write_reply, read_reply, expected):
    """A successful set response carries no proof of the observed property value."""
    address = property_packet(device)
    for reply in (write_reply, read_reply):
        if not reply or reply.get("code") != 0 or any(reply.get(k) != v for k, v in address.items()):
            return "unknown", None
    observed = read_reply.get("value")
    if type(observed) not in (int, float):
        return "unknown", None
    return ("confirmed" if observed == expected else "mismatch"), observed


class VirtualFamilyGateway:
    def __init__(self):
        self.devices = {d["id"]: deepcopy(d) for d in DEVICES}
        self.receipts = {}

    def snapshot(self):
        return deepcopy(list(self.devices.values()))

    def set_mode(self, device_id, mode):
        self.devices[device_id]["mode"] = mode

    def submit(self, action_id, device_id, value):
        """Remember uncertain results too. A repeated action never repeats a write."""
        if action_id in self.receipts:
            prior = self.receipts[action_id]
            if (prior["deviceId"], prior["requested"]) != (device_id, value):
                raise ValueError("action id reused for a different command")
            return deepcopy(prior)
        device = self.devices[device_id]
        cap = device["capability"]
        low, high, step = cap["valueRange"]
        observed = None
        packet = property_packet(device, value)
        write_reply = read_reply = None
        if "write" not in cap["access"] or not low <= value <= high or (value - low) % step:
            status = "rejected"
        elif device["mode"] == "offline":
            status = "offline"
        elif device["mode"] == "unknown":
            write_reply = {**property_packet(device), "code": 0}
            status, observed = decode_observation(device, write_reply, None, value)
        else:
            device["value"] = packet["value"]
            write_reply = {**property_packet(device), "code": 0}
            read_reply = {**property_packet(device, device["value"]), "code": 0}
            status, observed = decode_observation(device, write_reply, read_reply, value)
            device["lastObserved"] = observed
        result = {"actionId": action_id, "deviceId": device_id, "requested": value,
                  "status": status, "observed": observed, "source": "simulated",
                  "propertyRequest": packet, "writeReply": write_reply, "readReply": read_reply}
        self.receipts[action_id] = result
        return deepcopy(result)

"""Bind the demo's logical devices to property addresses for offline integration tests."""
import json
import os
from copy import deepcopy
from functools import partial
from pathlib import Path

from .gateway import DEVICES, VirtualFamilyGateway
from .service import FamilyEvening


def bind_addresses(bindings):
    devices = deepcopy(DEVICES)
    by_id = {device["id"]: device for device in devices}
    if not isinstance(bindings, list) or not bindings:
        raise ValueError("MIoT profile must be a nonempty array of property bindings")
    seen = set()
    for index, binding in enumerate(bindings):
        if not isinstance(binding, dict) or set(binding) != {"deviceId", "did", "siid", "piid"}:
            raise ValueError(f"Binding {index} requires deviceId, did, siid and piid")
        device_id, did = binding["deviceId"], binding["did"]
        if not isinstance(device_id, str) or device_id not in by_id or device_id in seen:
            raise ValueError(f"Unknown or repeated deviceId in binding {index}: {device_id!r}")
        if not isinstance(did, str) or not did or did.strip() != did:
            raise ValueError(f"Invalid did for {device_id}")
        for key in ("siid", "piid"):
            if type(binding[key]) is not int or binding[key] < 1:
                raise ValueError(f"{key} must be a positive integer for {device_id}")
        seen.add(device_id)
        by_id[device_id]["capability"].update(did=did, siid=binding["siid"], piid=binding["piid"])
    return devices


def create_family_session(profile_path=None):
    path = profile_path or os.environ.get("LIVINGMIND_FAMILY_MIOT_PROFILE")
    if not path:
        return FamilyEvening()
    try:
        bindings = json.loads(Path(path).read_text(encoding="utf-8"))
        devices = bind_addresses(bindings)
        return FamilyEvening(gateway_factory=partial(VirtualFamilyGateway, devices=devices))
    except (OSError, ValueError) as error:
        raise ValueError(f"Cannot load MIoT simulation profile {path}: {error}") from error

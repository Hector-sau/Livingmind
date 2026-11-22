"""Import MIoT Spec V2 property metadata from a supplied offline profile."""
from copy import deepcopy
from math import isfinite

from .gateway import supports_value


def _name(urn, kind):
    parts = urn.split(":") if isinstance(urn, str) else []
    if len(parts) < 5 or parts[0] != "urn" or parts[2] != kind or not parts[3]:
        raise ValueError(f"Invalid {kind} URN: {urn!r}")
    return parts[3]


def _iid(record, key="iid"):
    value = record.get(key)
    if type(value) is not int or value < 1:
        raise ValueError(f"Expected a positive integer {key}")
    return value


def _records(value, label):
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ValueError(f"Expected an array of {label}")
    return value


def _property(service, raw):
    access = raw.get("access")
    fmt = raw.get("format")
    if not isinstance(access, list) or any(a not in ("read", "write", "notify") for a in access):
        raise ValueError("Invalid MIoT property access")
    if not isinstance(fmt, str) or not fmt:
        raise ValueError("Expected a MIoT property format")
    prop = {"siid": _iid(service), "piid": _iid(raw), "service": _name(service.get("type"), "service"),
            "property": _name(raw.get("type"), "property"), "format": fmt, "access": list(access)}
    if "unit" in raw:
        if not isinstance(raw["unit"], str):
            raise ValueError("Invalid MIoT property unit")
        prop["unit"] = raw["unit"]
    if "value-range" in raw:
        bounds = raw["value-range"]
        if (not isinstance(bounds, list) or len(bounds) != 3
                or not all(type(n) in (int, float) and isfinite(n) for n in bounds)
                or bounds[0] > bounds[1] or bounds[2] <= 0):
            raise ValueError("Invalid MIoT value-range")
        prop["valueRange"] = list(bounds)
    if "value-list" in raw:
        options = _records(raw["value-list"], "MIoT value-list entries")
        if (not options or any(type(item.get("value")) is not int or not isinstance(item.get("description"), str)
                               for item in options)):
            raise ValueError("Expected integer MIoT enum values with descriptions")
        if len({item["value"] for item in options}) != len(options):
            raise ValueError("Repeated MIoT enum value")
        prop["valueList"] = [{"value": option["value"], "description": option["description"]} for option in options]
    return prop


def import_model(model, definition):
    """Normalize an embedded registry instance or its attributed property subset. No network I/O."""
    if not isinstance(model, str) or not model.strip() or not isinstance(definition, dict):
        raise ValueError("Expected a named model definition")
    instance = definition.get("instance")
    source = definition.get("source")
    if not isinstance(instance, dict) or not isinstance(source, str) or not source.strip():
        raise ValueError(f"Model {model} requires a source and an embedded instance")
    urn = instance.get("type")
    _name(urn, "device")
    properties = []
    seen_services = set()
    for service in _records(instance.get("services"), "MIoT services"):
        siid = _iid(service)
        if siid in seen_services:
            raise ValueError(f"Repeated service {siid} in {model}")
        seen_services.add(siid)
        _name(service.get("type"), "service")
        seen_props = set()
        for raw in _records(service.get("properties", []), "MIoT properties"):
            prop = _property(service, raw)
            if prop["piid"] in seen_props:
                raise ValueError(f"Repeated property in {model} service {siid}")
            seen_props.add(prop["piid"])
            properties.append(prop)
    if not properties:
        raise ValueError(f"No properties in {model}")
    return {"model": model, "urn": urn, "source": source, "properties": properties}


def bind_model_profile(devices, profile):
    """Map a verified logical capability to one property instance, preserving the entire supplied catalog."""
    if profile.get("format") != "miot-spec-v2" or not isinstance(profile.get("models"), dict):
        raise ValueError("Expected miot-spec-v2 format and embedded models")
    models = {name: import_model(name, entry) for name, entry in profile["models"].items()}
    bindings = _records(profile.get("bindings"), "model bindings")
    if not bindings:
        raise ValueError("Expected at least one model binding")
    by_id = {device["id"]: device for device in devices}
    seen = set()
    for binding in bindings:
        device_id, did, model = binding.get("deviceId"), binding.get("did"), binding.get("model")
        if not isinstance(device_id, str) or device_id not in by_id or device_id in seen:
            raise ValueError(f"Unknown or repeated logical device {device_id!r}")
        if not isinstance(did, str) or not did or did != did.strip():
            raise ValueError(f"Invalid did for {device_id}")
        if not isinstance(model, str) or model not in models:
            raise ValueError(f"Unknown model {model!r}")
        seen.add(device_id)
        address = (_iid(binding, "siid"), _iid(binding, "piid"))
        catalog = models[model]
        prop = next((p for p in catalog["properties"] if (p["siid"], p["piid"]) == address), None)
        device = by_id[device_id]
        expected = device["capability"]
        if prop is None or (prop["service"], prop["property"]) != (expected["service"], expected["property"]):
            raise ValueError(f"{model} {address} does not supply {device_id}'s expected service and property")
        unit = {"%": "percentage", "°C": "celsius", "档": None}[device["unit"]]
        if prop.get("unit") != unit or prop["format"] not in (
                "uint8", "uint16", "uint32", "uint64", "int8", "int16", "int32", "int64", "int", "float"):
            raise ValueError(f"Incompatible unit or numeric format for {device_id}")
        cap = {"did": did, **deepcopy(prop)}
        if "valueRange" not in cap:
            if "valueList" not in cap:
                raise ValueError(f"No numeric range or enum for {device_id}")
            values = [entry["value"] for entry in cap["valueList"]]
            # Existing UI clients use the bounds. The exact enum still governs every operation.
            cap["valueRange"] = [min(values), max(values), 1]
        initial = binding.get("initial", device["value"])
        if not supports_value(cap, initial):
            raise ValueError(f"Set an allowed simulated initial value for {device_id}")
        device.update(capability=cap, modelSpec=deepcopy(catalog), value=initial,
                      lastObserved=initial if "read" in cap["access"] else None)
    return devices

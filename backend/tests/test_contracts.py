from fastapi.testclient import TestClient

from app.contracts import Person, RestPreference
from app.main import create_app


def test_contracts_use_camel_case_on_the_wire():
    p = Person(
        person_id="p1",
        name="A",
        description="",
        rest_preference=RestPreference(light_brightness=20, ac_target_temp_c=24, curtain_open_percent=0),
    )
    dumped = p.model_dump(by_alias=True)
    assert "personId" in dumped and "restPreference" in dumped
    assert "acTargetTempC" in dumped["restPreference"]


def test_openapi_exposes_core_schemas():
    schemas = create_app().openapi()["components"]["schemas"]
    for name in ["Plan", "DeviceState", "Service", "ActivityRecord", "ErrorResponse", "RequestContext"]:
        assert name in schemas, name


def test_validation_errors_use_unified_format():
    client = TestClient(create_app())
    res = client.post("/api/plans/rest", json={"utterance": ""})
    assert res.status_code == 422
    body = res.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"

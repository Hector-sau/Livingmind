"""Step 6b: demo PIN switch, guest context, scene library."""

from app.demo import seed
from tests.conftest import ctx

SPACE = "space-home-bedroom"


def unlock(client, person, pin):
    return client.post(f"/api/persons/{person}/unlock", json={"accountId": "demo-account", "pin": pin})


def test_pin_right_wrong_and_unknown(client):
    ok = unlock(client, "person-lin", "2468")
    assert ok.status_code == 200 and ok.json()["unlocked"] is True
    assert "不是登录认证" in ok.json()["note"]

    bad = unlock(client, "person-lin", "0000")
    assert bad.status_code == 403 and bad.json()["error"]["code"] == "PIN_INVALID"
    assert "2468" not in bad.text

    assert unlock(client, "person-lin", None).status_code == 403
    assert unlock(client, "nobody", "1234").json()["error"]["code"] == "NOT_FOUND"
    wrong_account = client.post("/api/persons/person-lin/unlock", json={"accountId": "other", "pin": "2468"})
    assert wrong_account.status_code == 403


def test_pins_are_never_exposed(client):
    boot = client.get("/api/bootstrap", params={"accountId": "demo-account"})
    for pin in seed.PERSON_PINS.values():
        assert pin not in boot.text
    persons = {p["personId"]: p for p in boot.json()["persons"]}
    assert persons["person-lin"]["hasPin"] is True and persons["person-guest"]["hasPin"] is False


def test_guest_needs_no_pin_and_uses_space_defaults(client):
    assert unlock(client, "person-guest", None).status_code == 200
    plan = client.post("/api/plans/rest", json={"context": ctx("person-guest"), "utterance": "我想休息"}).json()
    assert "访客" in plan["summary"] and any("没有读取任何个人偏好" in n for n in plan["notes"])
    default = seed.SPACE_DEFAULT
    assert [a["value"] for a in plan["actions"]] == [
        default.light_brightness,
        default.ac_target_temp_c,
        default.curtain_open_percent,
    ]
    res = client.post(f"/api/plans/{plan['planId']}/confirm", json={"context": ctx("person-guest"), "planVersion": 1})
    assert res.status_code == 200
    stop = client.post(f"/api/services/{res.json()['service']['serviceId']}/stop", json={"context": ctx("person-guest")})
    assert stop.status_code == 200


def test_scene_library_status_is_honest(client):
    items = client.get("/api/scenes", params={"accountId": "demo-account"}).json()["items"]
    status = {s["sceneId"]: s["status"] for s in items}
    assert status == {"scene-rest": "implemented", "scene-room-temp": "implemented", "scene-wake": "planned"}
    wake = next(s for s in items if s["sceneId"] == "scene-wake")
    assert "尚未实现" in wake["verification"]
    # the planned scene has no backend entry point yet
    from app.api.routes import router

    paths = {r.path for r in router.routes}
    assert not any("wake" in p for p in paths)


def test_three_members_have_distinct_preferences_with_room_to_adjust():
    members = [p for p in seed.PERSONS if not p.is_guest]
    assert len(members) == 3
    prefs = {p.rest_preference.model_dump_json() for p in members}
    assert len(prefs) == 3
    for p in members:
        pref = p.rest_preference
        assert 16 + 3 <= pref.ac_target_temp_c <= 30 - 3  # ±3 °C band fits device limits
        assert pref.light_brightness <= 60  # rest plans stay dim

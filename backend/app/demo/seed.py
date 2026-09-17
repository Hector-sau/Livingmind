"""Seed data for the demo. Fictional people; preferences are preset, not learned."""

from app.contracts import DemoAccount, Person, RestPreference, Space

DEMO_ACCOUNT = DemoAccount(account_id="demo-account", display_name="演示账户", is_demo=True)

PERSONS: list[Person] = [
    Person(
        person_id="person-lin",
        name="林悦",
        description="喜欢暗一点、偏暖的休息环境",
        rest_preference=RestPreference(light_brightness=15, ac_target_temp_c=25, curtain_open_percent=0),
    ),
    Person(
        person_id="person-chen",
        name="陈川",
        description="怕热，习惯留一点窗帘缝",
        rest_preference=RestPreference(light_brightness=30, ac_target_temp_c=22, curtain_open_percent=10),
    ),
]

SPACES: list[Space] = [Space(space_id="space-home-bedroom", name="家 · 主卧")]

DEFAULT_SPACE_ID = SPACES[0].space_id

# Which persons and spaces the demo account may act on. Server-side check, not login.
MEMBERSHIPS: dict[str, dict[str, set[str]]] = {
    DEMO_ACCOUNT.account_id: {
        "persons": {p.person_id for p in PERSONS},
        "spaces": {s.space_id for s in SPACES},
    }
}

# Device state when the demo starts or is reset (bright room, warm, curtains open).
INITIAL_DEVICE_STATE = {"light_brightness": 80, "ac_target_temp_c": 26.0, "curtain_open_percent": 100}

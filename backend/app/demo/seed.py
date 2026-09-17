"""Demo seed data. Every person here is fictional; preferences are preset, not learned.

Design notes (see docs/test-data.md):
- Three household members with clearly different rest preferences, so the same sentence
  visibly produces different plans, plus one guest context that uses the space defaults.
- Preferences sit well inside device limits, leaving room for the ±3 °C / ±40 % adjustment
  band in both directions.
- Demo PINs only prevent accidental switching on a shared tablet. They are not authentication
  and the backend never uses them to authorise requests.
"""

from app.contracts import DemoAccount, Person, RestPreference, Scene, Space

DEMO_ACCOUNT = DemoAccount(account_id="demo-account", display_name="演示家庭", is_demo=True)

SPACE_DEFAULT = RestPreference(light_brightness=30, ac_target_temp_c=25, curtain_open_percent=0)

SPACES: list[Space] = [
    Space(space_id="space-home-bedroom", name="家 · 主卧", default_rest_preference=SPACE_DEFAULT),
]
DEFAULT_SPACE_ID = SPACES[0].space_id

GUEST_PERSON_ID = "person-guest"

PERSONS: list[Person] = [
    Person(
        person_id="person-lin",
        name="林悦",
        description="设计师，夜里怕亮，喜欢暗一点、偏暖的休息环境",
        rest_preference=RestPreference(light_brightness=15, ac_target_temp_c=25, curtain_open_percent=0),
        is_guest=False,
        has_pin=True,
        avatar_color="#4469F0",
    ),
    Person(
        person_id="person-chen",
        name="陈川",
        description="工程师，怕热，习惯留一点窗帘缝透气",
        rest_preference=RestPreference(light_brightness=30, ac_target_temp_c=22, curtain_open_percent=10),
        is_guest=False,
        has_pin=True,
        avatar_color="#24A67A",
    ),
    Person(
        person_id="person-zhou",
        name="周禾",
        description="早睡早起，喜欢保留一点自然光，室温偏暖",
        rest_preference=RestPreference(light_brightness=20, ac_target_temp_c=26.5, curtain_open_percent=25),
        is_guest=False,
        has_pin=True,
        avatar_color="#B7791F",
    ),
    Person(
        person_id=GUEST_PERSON_ID,
        name="访客",
        description="未选择个人账号：使用空间默认设置，不读取任何个人偏好",
        rest_preference=SPACE_DEFAULT,
        is_guest=True,
        has_pin=False,
        avatar_color="#66738A",
    ),
]

# Demo-only PINs. Never returned by any API.
PERSON_PINS: dict[str, str] = {"person-lin": "2468", "person-chen": "1357", "person-zhou": "8024"}

# Which persons and spaces the demo account may act on. Server-side check, not login.
MEMBERSHIPS: dict[str, dict[str, set[str]]] = {
    DEMO_ACCOUNT.account_id: {
        "persons": {p.person_id for p in PERSONS},
        "spaces": {s.space_id for s in SPACES},
    }
}

# Device state when the demo starts or is reset: evening, lights on, warm room, curtains open.
INITIAL_DEVICE_STATE = {"light_brightness": 80, "ac_target_temp_c": 26.0, "curtain_open_percent": 100}

# Scene library. Status must match what is actually implemented and tested.
SCENES: list[Scene] = [
    Scene(
        scene_id="scene-rest",
        title="我想休息",
        description="一句话生成休息计划，确认后调整灯光、空调和窗帘",
        status="implemented",
        verification="后端与前端测试、网页端到端验证；真机未验证",
        trigger="用户表达",
    ),
    Scene(
        scene_id="scene-room-temp",
        title="室温变化后自动调整",
        description="休息服务运行中，室温偏离设定时自动调整空调，有冷却时间和次数上限",
        status="implemented",
        verification="后端与前端测试、网页端到端验证（模拟事件，无真实传感器）；真机未验证",
        trigger="环境事件（模拟）",
    ),
    Scene(
        scene_id="scene-wake",
        title="起床渐进唤醒",
        description="按起床时间逐步打开窗帘、调亮灯光",
        status="planned",
        verification="尚未实现（计划在步骤 ⑦）",
        trigger="定时（规划中）",
    ),
]

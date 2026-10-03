"""Conservative guards for explicitly supported Chinese request patterns.

This is not general language understanding. Restrictions that the overnight planner
cannot preserve are clarified before any model call; recognised directional requests
are checked against the structured output, not trusted merely because JSON is valid.
"""

import re

from app.contracts import DeviceState, RestPreference

_DEVICES = re.compile(r"灯(?:光)?|空调|窗帘")
_NEGATED_ACTION = re.compile(
    r"(?:不要|别|不用|不许|禁止)(?:把|将)?(?:卧室的?)?"
    r"(?:(?:灯光?|空调|窗帘)(?:再)?)?(?:关|开|拉|调|变|动|设|亮|暗)"
)
_LIMITED = re.compile(r"(?:只|仅)(?:调|调整|控制)|其他.{0,3}(?:别|不要|不).{0,2}动|"
                      r"(?:灯光?|空调|窗帘|温度).{0,4}(?:保持现在|保持当前|不变)")


def request_clarification(text: str) -> str | None:
    t = re.sub(r"\s+", "", text)
    if _NEGATED_ACTION.search(t) or _LIMITED.search(t):
        return "我不会把限制条件当成操作。请直接说明要调整的设备和目标值，例如“空调调到 24 度”；这次不会启动整晚联动。"
    for clause in re.split(r"[，,。；;]", t):
        devices = {m.group().replace("灯光", "灯") for m in _DEVICES.finditer(clause)}
        if len(devices) == 1 and re.search(r"开.*关|关.*开|拉开.*拉上|拉上.*拉开", clause):
            return "这句话包含相反的操作。请说明你是想查询状态，还是设置一个明确的最终值。"
    return None


def directions(text: str) -> dict[str, int]:
    """Only recognise a direction when its device appears in the same clause."""
    found: dict[str, int] = {}
    for clause in re.split(r"[，,。；;]", re.sub(r"\s+", "", text)):
        for field, device, lower, higher in (
            ("light_brightness", r"灯|灯光", r"暗|柔和", r"亮"),
            ("ac_target_temp_c", r"空调|温度", r"凉|降|低", r"暖|升|高"),
            ("curtain_open_percent", r"窗帘", r"关|闭合|拉上", r"打开|拉开"),
        ):
            # Negation and preservation are deliberately handled by clarification.
            if not re.search(device, clause) or re.search(r"不|别|保持", clause):
                continue
            down, up = bool(re.search(lower, clause)), bool(re.search(higher, clause))
            if down != up:
                found[field] = -1 if down else 1
    return found


def direction_violation(text: str, preference: RestPreference, state: DeviceState,
                        proposed: RestPreference) -> str | None:
    # The system prompt defines the person's preference as the default baseline.
    # Explicit comparisons with current readings use those readings instead.
    baseline = state if re.search(r"比(?:现在|当前|刚才)", text) else preference
    bounds = {"light_brightness": (0, 100), "ac_target_temp_c": (16, 30), "curtain_open_percent": (0, 100)}
    for field, direction in directions(text).items():
        current, target = getattr(baseline, field), getattr(proposed, field)
        at_limit = current == bounds[field][0 if direction < 0 else 1]
        if (target - current) * direction < 0 or (target == current and not at_limit):
            return "模型建议与明确的调整方向不一致，请说明设备和目标值，例如“空调调到 24 度”。"
    return None

"""Unified executor: every device write goes through here (rule plans now, model plans later).

Checks per action, in order: service still valid (guard) -> tool whitelist -> parameter range
-> write -> read back. The guard runs before EACH action, so a stop that lands mid-plan
prevents the remaining actions.
"""

from __future__ import annotations

from typing import Callable, Optional

from app.adapters.virtual.devices import VirtualDeviceAdapter
from app.contracts import ActionResult, DeviceAction

# (device, command) -> (min, max, integer_only)
ALLOWED_COMMANDS: dict[tuple[str, str], tuple[float, float, bool]] = {
    ("light", "set_brightness"): (0, 100, True),
    ("ac", "set_target_temperature"): (16, 30, False),
    ("curtain", "set_open_percent"): (0, 100, True),
}

Guard = Callable[[], Optional[str]]
OnResult = Callable[[DeviceAction, ActionResult], None]


def validate_action(action: DeviceAction) -> Optional[str]:
    rule = ALLOWED_COMMANDS.get((action.device, action.command))
    if rule is None:
        return f"工具不在白名单：{action.device}.{action.command}"
    low, high, integer_only = rule
    if not (low <= action.value <= high):
        return f"参数超出范围：{action.value}（允许 {low}–{high}）"
    if integer_only and float(action.value) != int(action.value):
        return f"参数必须是整数：{action.value}"
    return None


class Executor:
    def __init__(self, adapter: VirtualDeviceAdapter):
        self._adapter = adapter

    def run(self, actions: list[DeviceAction], guard: Guard, on_result: OnResult) -> list[ActionResult]:
        results: list[ActionResult] = []
        for action in actions:
            result = self._run_one(action, guard)
            on_result(action, result)
            results.append(result)
        return results

    def _run_one(self, action: DeviceAction, guard: Guard) -> ActionResult:
        base = dict(action_id=action.action_id, device=action.device, command=action.command, value=action.value)
        stop_reason = guard()
        if stop_reason:
            return ActionResult(**base, outcome="skipped", reason=stop_reason, observed_value=None)
        invalid = validate_action(action)
        if invalid:
            return ActionResult(**base, outcome="rejected", reason=invalid, observed_value=None)
        try:
            self._adapter.write(action.device, action.command, action.value)
        except Exception as exc:  # device failure is reported, not hidden
            return ActionResult(**base, outcome="failed", reason=str(exc), observed_value=None)
        observed = self._adapter.read_value(action.device)
        if float(observed) != float(action.value):
            return ActionResult(**base, outcome="failed", reason="回读值与目标不一致", observed_value=observed)
        return ActionResult(**base, outcome="succeeded", reason=None, observed_value=observed)

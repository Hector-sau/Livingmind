"""Unified executor: every rule- or model-derived device write goes through here.

Checks per action, in order: service guard -> platform policy -> bounded grant -> durable
command transition -> gateway receipt -> readback. The guard runs before EACH action, so a
stop that lands mid-plan prevents the remaining actions.
"""

from __future__ import annotations

from datetime import datetime
import time
from typing import Callable, Optional

from app.adapters.gateway import AdapterDeviceGateway
from app.adapters.protocol import DeviceAdapter, DeviceCommandReceipt, DeviceCommandRequest, DeviceGateway
from app.clock import Clock, utc_now
from app.contracts import ActionExecution, ActionResult, DeviceAction, ExecutionGrant
from app.harness.grants import grant_denial_reason
from app.harness.policy import validate_action
from app.observability.events import record

Guard = Callable[[], Optional[str]]
OnResult = Callable[[DeviceAction, ActionResult], None]
OnExecution = Callable[[ActionExecution], None]


class Executor:
    def __init__(
        self,
        adapter: DeviceAdapter,
        *,
        gateway: Optional[DeviceGateway] = None,
        clock: Clock = utc_now,
        execution_guard: Optional[Guard] = None,
    ):
        self._adapter = adapter
        self._gateway = gateway or AdapterDeviceGateway(adapter)
        self._clock = clock
        self._execution_guard = execution_guard

    def run(
        self,
        actions: list[DeviceAction],
        guard: Guard,
        on_result: OnResult,
        *,
        grant: Optional[ExecutionGrant] = None,
        plan_id: str = "legacy",
        service_id: Optional[str] = None,
        service_epoch: int = 0,
        on_execution: Optional[OnExecution] = None,
    ) -> list[ActionResult]:
        results: list[ActionResult] = []
        for action in actions:
            started = time.monotonic()
            result = self._run_one(
                action,
                guard,
                grant=grant,
                plan_id=plan_id,
                service_id=service_id,
                service_epoch=service_epoch,
                on_execution=on_execution,
            )
            record(
                "action.finished", planId=plan_id, serviceId=service_id,
                actionId=action.action_id, outcome=result.outcome,
                durationMs=round((time.monotonic() - started) * 1000, 3),
            )
            on_result(action, result)
            results.append(result)
        return results

    def _run_one(
        self,
        action: DeviceAction,
        guard: Guard,
        *,
        grant: Optional[ExecutionGrant],
        plan_id: str,
        service_id: Optional[str],
        service_epoch: int,
        on_execution: Optional[OnExecution],
    ) -> ActionResult:
        base = dict(action_id=action.action_id, device=action.device, command=action.command, value=action.value)
        execution = None
        if grant is not None:
            execution = ActionExecution(
                action_id=action.action_id,
                grant_id=grant.grant_id,
                plan_id=plan_id,
                service_id=service_id,
                space_id=grant.space_id,
                device=action.device,
                command=action.command,
                requested_value=action.value,
                service_epoch=service_epoch,
                status="pending",
                attempt_count=0,
                requested_at=self._clock(),
            )
            self._transition(execution, on_execution)
        stop_reason = (self._execution_guard() if self._execution_guard else None) or guard()
        if stop_reason:
            self._finish(execution, "cancelled", error_detail=stop_reason, on_execution=on_execution)
            return ActionResult(**base, outcome="skipped", reason=stop_reason, observed_value=None)
        invalid = validate_action(action)
        if invalid:
            self._finish(execution, "rejected", error_kind="policy", error_detail=invalid, on_execution=on_execution)
            return ActionResult(**base, outcome="rejected", reason=invalid, observed_value=None)
        if grant is not None:
            invalid = grant_denial_reason(
                grant,
                action,
                now=self._clock(),
                service_epoch=service_epoch,
                service_id=service_id,
            )
            if invalid:
                self._finish(execution, "rejected", error_kind="grant", error_detail=invalid, on_execution=on_execution)
                return ActionResult(**base, outcome="rejected", reason=invalid, observed_value=None)

        if execution is not None:
            execution.status = "dispatching"
            execution.attempt_count += 1
            self._transition(execution, on_execution)
        try:
            receipt = self._gateway.submit(
                DeviceCommandRequest(
                    action_id=action.action_id,
                    service_id=service_id,
                    service_epoch=service_epoch,
                    device_id=f"{self._adapter.space_id}:{action.device}",
                    device_type=action.device,
                    command=action.command,
                    value=action.value,
                    requested_at=self._clock(),
                )
            )
        except OSError as exc:
            receipt = self._transport_unknown(action.action_id, exc)
        if receipt.action_id != action.action_id:
            receipt = self._mismatched_receipt(action.action_id)
        if receipt.status == "accepted":
            if execution is not None:
                execution.status = "accepted"
                execution.accepted_at = self._clock()
                self._transition(execution, on_execution)
            try:
                receipt = self._gateway.query(action.action_id) or receipt
            except OSError as exc:
                receipt = self._transport_unknown(action.action_id, exc)
            if receipt.action_id != action.action_id:
                receipt = self._mismatched_receipt(action.action_id)
        if receipt.status in ("accepted", "unknown"):
            self._finish(
                execution,
                "unknown",
                error_kind=receipt.error_kind or "unknown",
                error_detail=receipt.detail or "设备结果尚未确定",
                on_execution=on_execution,
            )
            return ActionResult(**base, outcome="unknown", reason=receipt.detail or "设备结果尚未确定", observed_value=None)
        if receipt.status in ("rejected", "failed"):
            status = "rejected" if receipt.status == "rejected" else "failed"
            self._finish(
                execution,
                status,
                error_kind=receipt.error_kind,
                error_detail=receipt.detail,
                on_execution=on_execution,
            )
            return ActionResult(**base, outcome=status, reason=receipt.detail or "设备拒绝执行", observed_value=None)

        observed = receipt.observed_value
        if observed is None or float(observed) != float(action.value):
            reason = "回读值与目标不一致" if observed is not None else "设备完成回执缺少观测值"
            self._finish(
                execution,
                "failed",
                observed_value=observed,
                observed_at=receipt.observed_at,
                error_kind="readback_mismatch",
                error_detail=reason,
                on_execution=on_execution,
            )
            return ActionResult(**base, outcome="failed", reason=reason, observed_value=observed)
        self._finish(
            execution,
            "completed",
            observed_value=observed,
            observed_at=receipt.observed_at,
            on_execution=on_execution,
        )
        return ActionResult(**base, outcome="succeeded", reason=None, observed_value=observed)

    @staticmethod
    def _mismatched_receipt(action_id: str) -> DeviceCommandReceipt:
        return DeviceCommandReceipt(action_id, "unknown", None, None, "unknown",
                                    "设备回执不属于当前动作，结果待核对；未自动重试")

    @staticmethod
    def _transport_unknown(action_id: str, exc: OSError) -> DeviceCommandReceipt:
        # A transport failure can occur after the physical write. Never infer "failed"
        # or resend from a missing reply; persist unknown and let reconciliation decide.
        return DeviceCommandReceipt(
            action_id=action_id,
            status="unknown",
            observed_value=None,
            observed_at=None,
            error_kind="timeout" if isinstance(exc, TimeoutError) else "offline",
            detail="设备网关回执未确认，动作结果未知；未自动重试",
        )

    @staticmethod
    def _transition(execution: Optional[ActionExecution], callback: Optional[OnExecution]) -> None:
        if execution is not None and callback is not None:
            callback(execution.model_copy(deep=True))

    def _finish(
        self,
        execution: Optional[ActionExecution],
        status,
        *,
        observed_value=None,
        observed_at: Optional[datetime] = None,
        error_kind=None,
        error_detail=None,
        on_execution: Optional[OnExecution],
    ) -> None:
        if execution is None:
            return
        execution.status = status
        execution.completed_at = self._clock()
        execution.observed_value = observed_value
        execution.observed_at = observed_at
        execution.error_kind = error_kind
        execution.error_detail = error_detail
        self._transition(execution, on_execution)

"""Rest-service lifecycle: plan -> confirm -> execute -> active -> stop.

Locking model:
- Bookkeeping (plans, services, epochs, activity) changes only under ``self._lock``.
- Device writes run OUTSIDE that lock, so a stop request is never blocked by a slow device.
- Before every device action the executor's guard re-checks, under the lock, that the
  service is still active and the space epoch is unchanged; a stop bumps the epoch.
Front-end mock (apps/mobile/services/mock/mockApi.ts) mirrors the visible rules.
"""

from __future__ import annotations

import threading
from typing import Optional

from app.adapters.virtual.devices import VirtualDeviceAdapter
from app.api.errors import ApiError
from app.clock import Clock, utc_now
from app.contracts import (
    ActionResult,
    ActivityKind,
    ActivityRecord,
    ActivitySource,
    BootstrapResponse,
    ConfirmPlanResponse,
    DeviceAction,
    DeviceState,
    Person,
    Plan,
    RequestContext,
    Service,
    StopServiceResponse,
)
from app.demo import seed
from app.harness.executor import Executor
from app.repositories.memory_store import MemoryStore, PlanRecord
from app.rules.rest_rule import build_rest_plan


class RestService:
    def __init__(self, clock: Clock = utc_now):
        self._clock = clock
        self._lock = threading.RLock()
        self._store = MemoryStore()
        self._devices = {
            s.space_id: VirtualDeviceAdapter(s.space_id, seed.INITIAL_DEVICE_STATE, clock) for s in seed.SPACES
        }

    # ---- identity (demo only, not authentication) ----

    def _check_account(self, account_id: str) -> None:
        if account_id not in seed.MEMBERSHIPS:
            raise ApiError("FORBIDDEN_CONTEXT", "演示账户不存在")

    def _check_space(self, account_id: str, space_id: str) -> None:
        self._check_account(account_id)
        if space_id not in seed.MEMBERSHIPS[account_id]["spaces"]:
            raise ApiError("FORBIDDEN_CONTEXT", "该空间不属于演示账户", {"spaceId": space_id})

    def _check_context(self, ctx: RequestContext) -> Person:
        self._check_space(ctx.account_id, ctx.space_id)
        if ctx.person_id not in seed.MEMBERSHIPS[ctx.account_id]["persons"]:
            raise ApiError("FORBIDDEN_CONTEXT", "该人物不属于演示账户", {"personId": ctx.person_id})
        return next(p for p in seed.PERSONS if p.person_id == ctx.person_id)

    # ---- helpers ----

    def _log(
        self,
        space_id: str,
        kind: ActivityKind,
        source: ActivitySource,
        message: str,
        *,
        service_id: Optional[str] = None,
        plan_id: Optional[str] = None,
        person_id: Optional[str] = None,
        action: Optional[ActionResult] = None,
    ) -> None:
        self._store.activity.append(
            ActivityRecord(
                activity_id=self._store.new_id("evt"),
                timestamp=self._clock(),
                space_id=space_id,
                kind=kind,
                source=source,
                message=message,
                service_id=service_id,
                plan_id=plan_id,
                person_id=person_id,
                action=action,
            )
        )

    def _bootstrap(self) -> BootstrapResponse:
        space_id = seed.DEFAULT_SPACE_ID
        return BootstrapResponse(
            mode="demo",
            account=seed.DEMO_ACCOUNT,
            persons=seed.PERSONS,
            spaces=seed.SPACES,
            default_space_id=space_id,
            device_state=self._devices[space_id].read_state(),
            active_service=self._store.active_service(space_id),
        )

    # ---- public operations ----

    def bootstrap(self, account_id: str) -> BootstrapResponse:
        self._check_account(account_id)
        with self._lock:
            return self._bootstrap()

    def device_state(self, account_id: str, space_id: str) -> DeviceState:
        self._check_space(account_id, space_id)
        with self._lock:
            return self._devices[space_id].read_state()

    def create_rest_plan(self, ctx: RequestContext, utterance: str) -> Plan:
        person = self._check_context(ctx)
        with self._lock:
            plan = build_rest_plan(person, ctx.space_id, utterance, self._clock(), self._store.new_id)
            self._store.plans[plan.plan_id] = PlanRecord(plan=plan, epoch=self._store.epoch(ctx.space_id))
            self._log(
                ctx.space_id,
                "plan_created",
                "rule_engine",
                f"生成休息计划（{person.name}，规则）",
                plan_id=plan.plan_id,
                person_id=person.person_id,
            )
            return plan

    def _reject(self, record: PlanRecord, code, message: str) -> ApiError:
        plan = record.plan
        self._log(plan.space_id, "plan_rejected", "system", message, plan_id=plan.plan_id, person_id=plan.person_id)
        return ApiError(code, message, {"planId": plan.plan_id})

    def confirm_plan(self, plan_id: str, ctx: RequestContext, plan_version: int) -> ConfirmPlanResponse:
        self._check_context(ctx)
        with self._lock:
            record = self._store.plans.get(plan_id)
            if record is None:
                raise ApiError("NOT_FOUND", "计划不存在", {"planId": plan_id})
            plan = record.plan
            if plan.space_id != ctx.space_id or plan.person_id != ctx.person_id:
                raise ApiError("FORBIDDEN_CONTEXT", "计划不属于当前人物或空间", {"planId": plan_id})
            if plan.version != plan_version:
                raise self._reject(record, "PLAN_VERSION_MISMATCH", "计划版本已变化，请刷新")

            # Idempotent: an executed (or currently executing) plan is never executed again.
            if plan.status == "executed":
                service = self._store.services[record.service_id]  # type: ignore[index]
                self._log(
                    plan.space_id,
                    "plan_confirm_repeated",
                    "system",
                    "重复确认，未再次执行",
                    service_id=service.service_id,
                    plan_id=plan_id,
                    person_id=plan.person_id,
                )
                return ConfirmPlanResponse(
                    plan=plan,
                    service=service,
                    results=list(record.results),
                    device_state=self._devices[plan.space_id].read_state(),
                    repeated=True,
                )

            if plan.status == "invalidated" or record.epoch != self._store.epoch(plan.space_id):
                plan.status = "invalidated"
                raise self._reject(record, "PLAN_INVALIDATED", "计划已失效（服务停止后需重新生成）")
            if plan.status == "expired" or self._clock() > plan.expires_at:
                plan.status = "expired"
                raise self._reject(record, "PLAN_EXPIRED", "计划已过期，请重新生成")
            if self._store.active_service(plan.space_id):
                raise self._reject(record, "SERVICE_ALREADY_ACTIVE", "当前空间已有运行中的服务，请先停止")

            now = self._clock()
            service = Service(
                service_id=self._store.new_id("svc"),
                space_id=plan.space_id,
                person_id=plan.person_id,
                plan_id=plan_id,
                plan_version=plan.version,
                status="active",
                started_at=now,
                stopped_at=None,
            )
            self._store.services[service.service_id] = service
            plan.status = "executed"
            record.service_id = service.service_id
            record.results = []
            self._log(
                plan.space_id,
                "plan_confirmed",
                "user",
                "用户确认执行休息计划",
                service_id=service.service_id,
                plan_id=plan_id,
                person_id=plan.person_id,
            )
            epoch_at_start = self._store.epoch(plan.space_id)
            actions = list(plan.actions)

        # Lock released: device writes may be slow, and a stop must be able to land meanwhile.
        self._execute(service, actions, epoch_at_start, record)

        with self._lock:
            return ConfirmPlanResponse(
                plan=plan,
                service=service,
                results=list(record.results),
                device_state=self._devices[plan.space_id].read_state(),
                repeated=False,
            )

    def _execute(self, service: Service, actions: list[DeviceAction], epoch_at_start: int, record: PlanRecord) -> None:
        def guard() -> Optional[str]:
            # Re-check under the lock right before each external write.
            with self._lock:
                if service.status != "active":
                    return "服务已停止"
                if self._store.epoch(service.space_id) != epoch_at_start:
                    return "计划版本已失效"
                return None

        def on_result(action: DeviceAction, result: ActionResult) -> None:
            ok = result.outcome == "succeeded"
            with self._lock:
                record.results.append(result)
                self._log(
                    service.space_id,
                    "action_executed" if ok else "action_rejected",
                    "virtual_device" if ok else "executor",
                    f"{action.label}（回读 {result.observed_value:g}）" if ok else f"{action.label}：{result.reason}",
                    service_id=service.service_id,
                    plan_id=service.plan_id,
                    person_id=service.person_id,
                    action=result,
                )

        Executor(self._devices[service.space_id]).run(actions, guard, on_result)

    def stop_service(self, service_id: str, ctx: RequestContext) -> StopServiceResponse:
        self._check_context(ctx)
        with self._lock:
            service = self._store.services.get(service_id)
            if service is None or service.space_id != ctx.space_id:
                raise ApiError("NOT_FOUND", "服务不存在", {"serviceId": service_id})
            if service.status != "active":
                raise ApiError("SERVICE_NOT_ACTIVE", "服务已经停止", {"serviceId": service_id})
            service.status = "stopped"
            service.stopped_at = self._clock()
            # Invalidate every plan created before this stop (they cannot restart the service).
            self._store.epochs[service.space_id] = self._store.epoch(service.space_id) + 1
            for rec in self._store.plans.values():
                if rec.plan.space_id == service.space_id and rec.plan.status == "proposed":
                    rec.plan.status = "invalidated"
            self._log(
                service.space_id,
                "service_stopped",
                "user",
                "用户停止服务，设备保持当前状态",
                service_id=service_id,
                plan_id=service.plan_id,
                person_id=service.person_id,
            )
            # Default: keep devices as they are (no automatic restore).
            return StopServiceResponse(service=service, device_state=self._devices[service.space_id].read_state())

    def activity(self, account_id: str, space_id: str, limit: int) -> list[ActivityRecord]:
        self._check_space(account_id, space_id)
        with self._lock:
            items = [a for a in self._store.activity if a.space_id == space_id]
            return list(reversed(items))[:limit]

    def reset(self, account_id: str) -> BootstrapResponse:
        self._check_account(account_id)
        with self._lock:
            self._store.clear()
            for adapter in self._devices.values():
                adapter.reset()
            return self._bootstrap()


_service: Optional[RestService] = None


def get_rest_service() -> RestService:
    global _service
    if _service is None:
        _service = RestService()
    return _service

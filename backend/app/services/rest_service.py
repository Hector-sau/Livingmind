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
from datetime import timedelta
from typing import Optional

from app import config
from app.adapters.virtual.devices import VirtualDeviceAdapter
from app.api.errors import ApiError
from app.clock import Clock, utc_now
from app.contracts import (
    ActionResult,
    PlannerMode,
    ActivityKind,
    ActivityRecord,
    ActivitySource,
    BootstrapResponse,
    ConfirmPlanResponse,
    DeviceAction,
    DeviceState,
    EventResult,
    EventType,
    Person,
    Plan,
    RequestContext,
    Scene,
    Service,
    UnlockPersonResponse,
    StopServiceResponse,
)
from app.demo import seed
from app.harness.executor import Executor
from app.repositories.memory_store import MemoryStore, PlanRecord
from app.services.planner import Planner, planner_from_config


class RestService:
    def __init__(
        self,
        clock: Clock = utc_now,
        planner: Optional[Planner] = None,
        event_cooldown_s: Optional[float] = None,
        event_max_adjustments: Optional[int] = None,
    ):
        self._clock = clock
        self._cooldown = timedelta(seconds=config.EVENT_COOLDOWN_S if event_cooldown_s is None else event_cooldown_s)
        self._max_adjustments = config.EVENT_MAX_ADJUSTMENTS if event_max_adjustments is None else event_max_adjustments
        self._lock = threading.RLock()
        self._store = MemoryStore()
        self._planner = planner or planner_from_config(clock)
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
            planner=self._planner.info(),
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

    def unlock_person(self, account_id: str, person_id: str, pin: Optional[str]) -> UnlockPersonResponse:
        """Demo PIN check for switching person on a shared tablet. Not authentication:
        no token is issued and later requests are not authorised by it."""
        self._check_account(account_id)
        if person_id not in seed.MEMBERSHIPS[account_id]["persons"]:
            raise ApiError("NOT_FOUND", "人物不存在", {"personId": person_id})
        expected = seed.PERSON_PINS.get(person_id)
        if expected is not None and pin != expected:
            raise ApiError("PIN_INVALID", "PIN 不正确", {"personId": person_id})
        return UnlockPersonResponse(
            person_id=person_id,
            unlocked=True,
            note="演示用 PIN，仅防止共享平板上误切换，不是登录认证",
        )

    def scenes(self, account_id: str) -> list[Scene]:
        self._check_account(account_id)
        return list(seed.SCENES)

    def device_state(self, account_id: str, space_id: str) -> DeviceState:
        self._check_space(account_id, space_id)
        with self._lock:
            return self._devices[space_id].read_state()

    def create_rest_plan(self, ctx: RequestContext, utterance: str, mode: Optional[PlannerMode] = None) -> Plan:
        person = self._check_context(ctx)
        # Planning may call a model (slow): do it outside the lock. Only bookkeeping is locked.
        device_state = self._devices[ctx.space_id].read_state()
        outcome = self._planner.plan(person, ctx.space_id, utterance, device_state, self._store.new_id, mode)
        plan = outcome.plan
        with self._lock:
            self._store.plans[plan.plan_id] = PlanRecord(plan=plan, epoch=self._store.epoch(ctx.space_id))
            gen = plan.generation
            if plan.source == "model":
                self._log(
                    ctx.space_id,
                    "plan_created",
                    "experience_agent",
                    f"模型生成休息计划（{person.name}，{gen.provider}/{gen.model}，{gen.latency_ms} ms）",
                    plan_id=plan.plan_id,
                    person_id=person.person_id,
                )
            else:
                if outcome.fallback_reason:
                    self._log(
                        ctx.space_id,
                        "plan_fallback",
                        "system",
                        f"模型计划未采用，改用规则：{outcome.fallback_reason}（{gen.latency_ms} ms）",
                        plan_id=plan.plan_id,
                        person_id=person.person_id,
                    )
                self._log(
                    ctx.space_id,
                    "plan_created",
                    "rule_engine",
                    f"生成休息计划（{person.name}，{'规则降级' if outcome.fallback_reason else '规则'}）",
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
                planner_mode=plan.generation.mode_requested,
                adjustments=0,
                last_adjusted_at=None,
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

    # ---- environment events (step 6) ----

    def inject_event(self, space_id: str, ctx: RequestContext, event_type: EventType, room_temp_c: float) -> EventResult:
        """Simulated room-temperature event -> at most one automatic adjustment of the active service."""
        self._check_context(ctx)
        if ctx.space_id != space_id:
            raise ApiError("FORBIDDEN_CONTEXT", "事件空间与请求上下文不一致", {"spaceId": space_id})
        adapter = self._devices[space_id]

        def ignored(event_id: str, reason: str, service: Optional[Service]) -> EventResult:
            self._log(
                space_id,
                "event_ignored",
                "system",
                f"事件已忽略：{reason}",
                service_id=service.service_id if service else None,
                person_id=service.person_id if service else None,
            )
            return EventResult(
                event_id=event_id,
                source="simulated",
                outcome="ignored",
                reason=reason,
                service=service,
                plan=None,
                results=[],
                device_state=adapter.read_state(),
            )

        with self._lock:
            event_id = self._store.new_id("event")
            service = self._store.active_service(space_id)
            self._log(
                space_id,
                "event_received",
                "simulated_event",
                f"模拟事件：室温变为 {room_temp_c:g}°C",
                service_id=service.service_id if service else None,
            )
            now = self._clock()
            if service is None:
                return ignored(event_id, "当前没有运行中的服务", None)
            if service.service_id in self._store.replanning:
                return ignored(event_id, "上一次调整仍在进行", service)
            if service.adjustments >= self._max_adjustments:
                return ignored(event_id, f"本次服务已调整 {service.adjustments} 次，达到上限", service)
            if service.last_adjusted_at and now - service.last_adjusted_at < self._cooldown:
                left = int((self._cooldown - (now - service.last_adjusted_at)).total_seconds()) + 1
                return ignored(event_id, f"冷却中，约 {left} 秒后才会再次调整", service)
            self._store.replanning.add(service.service_id)
            epoch_at_start = self._store.epoch(space_id)
            person = next(p for p in seed.PERSONS if p.person_id == service.person_id)
            mode = service.planner_mode

        try:
            # Planning (possibly a model call) happens outside the lock.
            outcome = self._planner.plan_adjustment(
                person, space_id, room_temp_c, adapter.read_state(), self._store.new_id, mode
            )
            plan = outcome.plan
            with self._lock:
                if service.status != "active" or self._store.epoch(space_id) != epoch_at_start:
                    return ignored(event_id, "规划期间服务已停止", service)
                record = PlanRecord(plan=plan, epoch=epoch_at_start, service_id=service.service_id)
                self._store.plans[plan.plan_id] = record
                if outcome.fallback_reason:
                    self._log(
                        space_id,
                        "plan_fallback",
                        "system",
                        f"模型计划未采用，改用调整规则：{outcome.fallback_reason}（{plan.generation.latency_ms} ms）",
                        service_id=service.service_id,
                        plan_id=plan.plan_id,
                        person_id=person.person_id,
                    )
                if not plan.actions:
                    plan.status = "executed"
                    return ignored(event_id, plan.summary, service)
                plan.status = "executed"
                service.adjustments += 1
                service.last_adjusted_at = self._clock()
                label = {"model": "模型", "rule": "规则", "rule_fallback": "规则降级"}.get(plan.source, plan.source)
                self._log(
                    space_id,
                    "service_adjusted",
                    "experience_agent" if plan.source == "model" else "rule_engine",
                    f"自动调整（{label}）：{plan.summary}",
                    service_id=service.service_id,
                    plan_id=plan.plan_id,
                    person_id=person.person_id,
                )
                actions = list(plan.actions)

            self._execute(service, actions, epoch_at_start, record)

            with self._lock:
                return EventResult(
                    event_id=event_id,
                    source="simulated",
                    outcome="adjusted",
                    reason=None,
                    service=service,
                    plan=plan,
                    results=list(record.results),
                    device_state=adapter.read_state(),
                )
        finally:
            with self._lock:
                self._store.replanning.discard(service.service_id)

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
                self._log(adapter.space_id, "demo_reset", "system", "演示数据已重置（内存数据与虚拟设备回到初始状态）")
            return self._bootstrap()


_service: Optional[RestService] = None


def get_rest_service() -> RestService:
    global _service
    if _service is None:
        _service = RestService()
    return _service

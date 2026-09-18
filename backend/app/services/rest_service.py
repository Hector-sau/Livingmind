"""Rest-service lifecycle: message -> main Agent plan -> confirm -> execute -> active -> stop.

Planning is delegated to the main Agent (agents/orchestrator), which coordinates memory,
the Experience Agent, Energy Intelligence, the Space Execution Agent and the Harness pre-check.

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
from app.cache import Cooldown, SpaceLock
from app.api.errors import ApiError
from app.clock import Clock, utc_now
from app.agents.orchestrator import Orchestrator
from app.agents.space_execution import SpaceExecutionAgent
from app.contracts import (
    ActionResult,
    AdvanceClockResponse,
    ScheduledStep,
    AssistantReply,
    EnergyMode,
    MemoryView,
    OfflineEnergySimulation,
    PlannerMode,
    RestPreference,
    Space,
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
    WakeTime,
)
from app.demo import seed
from app.energy import EnergyIntelligence
from app.events.envelope import event as domain_event
from app.energy.simulation import offline_energy_simulation
from app.harness.executor import Executor
from app.db.session import database_configured
from app.memory import MemoryService
from app.memory.repository import InMemoryPreferenceRepository, PreferenceRepository, SqlPreferenceRepository
from app.repositories.store import FLAG_ADVANCING, FLAG_REPLANNING, MemoryStore, PlanRecord, Store
from app.repositories.sql_store import SqlStore
from app.rules.night_rule import clock_label
from app.services.planner import Planner, planner_from_config


def default_preference_repository() -> PreferenceRepository:
    """PostgreSQL when configured, otherwise the in-memory demo store."""
    return SqlPreferenceRepository() if database_configured() else InMemoryPreferenceRepository()


def default_store() -> Store:
    """PostgreSQL when configured, otherwise the in-memory demo store."""
    return SqlStore() if database_configured() else MemoryStore()


class RestService:
    def __init__(
        self,
        clock: Clock = utc_now,
        planner: Optional[Planner] = None,
        event_cooldown_s: Optional[float] = None,
        event_max_adjustments: Optional[int] = None,
        preferences: Optional[PreferenceRepository] = None,
        store: Optional[Store] = None,
    ):
        self._clock = clock
        self._cooldown = timedelta(seconds=config.EVENT_COOLDOWN_S if event_cooldown_s is None else event_cooldown_s)
        self._max_adjustments = config.EVENT_MAX_ADJUSTMENTS if event_max_adjustments is None else event_max_adjustments
        self._lock = threading.RLock()
        self._store: Store = store or default_store()
        self._planner = planner or planner_from_config(clock)
        self._devices = {
            s.space_id: VirtualDeviceAdapter(s.space_id, seed.INITIAL_DEVICE_STATE, clock) for s in seed.SPACES
        }
        self._memory = MemoryService(clock, preferences or default_preference_repository())
        # Redis (optional): a short cross-instance lock and a fast cooldown check. The database
        # constraints and the executor guard remain the real protection.
        self._cooldown_cache = Cooldown(self._cooldown.total_seconds())
        self._energy_modes: dict[str, EnergyMode] = {s.space_id: s.energy_mode for s in seed.SPACES}
        self._legacy_agent = Orchestrator(
            planner=self._planner,
            memory=self._memory,
            energy=EnergyIntelligence(
                seed.OUTDOOR_TEMP_C, seed.PEAK_HOURS_LOCAL, config.LOCAL_UTC_OFFSET_HOURS, config.DEMO_LOCAL_HOUR
            ),
            space_execution=SpaceExecutionAgent(seed.NIGHT_LIGHT_MAX),
            clock=clock,
        )
        self._agent = self._legacy_agent
        if config.ORCHESTRATOR == "langgraph":
            # Same stages, run as a graph with checkpoints (T3). Device execution stays here.
            from app.graph.runtime import GraphOrchestrator

            self._agent = GraphOrchestrator(self._legacy_agent, lambda space_id: self._devices[space_id])

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

    def _space_lock(self, space_id: str) -> SpaceLock:
        """Hold while this request may write devices. A no-op when Redis is not configured."""
        return SpaceLock(space_id)

    @staticmethod
    def _busy(space_id: str) -> ApiError:
        return ApiError("SPACE_BUSY", "这个空间正在执行另一个请求，请稍后重试", {"spaceId": space_id})

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
        self._store.append_activity(
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

    def _space(self, space: Space) -> Space:
        return space.model_copy(update={"energy_mode": self._energy_modes[space.space_id]})

    def _bootstrap(self) -> BootstrapResponse:
        space_id = seed.DEFAULT_SPACE_ID
        return BootstrapResponse(
            mode="demo",
            planner=self._planner.info(),
            account=seed.DEMO_ACCOUNT,
            # Shared listing: no personal preferences (read your own via the memory endpoint).
            persons=[p.model_copy(update={"rest_preference": None}) for p in seed.PERSONS],
            spaces=[self._space(s) for s in seed.SPACES],
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

    def offline_energy_simulation(self, account_id: str, space_id: str) -> OfflineEnergySimulation:
        """Read-only offline evidence; no model is loaded and no current device state is changed."""
        self._check_space(account_id, space_id)
        return offline_energy_simulation()

    def handle_message(
        self,
        ctx: RequestContext,
        text: str,
        mode: Optional[PlannerMode] = None,
        force_rest: bool = False,
        wake_time: WakeTime = "07:00",
    ) -> AssistantReply:
        """Main entry for the chat: the main Agent decides the branch and returns a plan or an answer."""
        self._check_context(ctx)
        # Capture this before the (possibly slow) model call. A stop increments the
        # epoch, so a request that began before stop can never resurrect a service.
        with self._lock:
            request_epoch = self._store.epoch(ctx.space_id)
        # Planning may call a model (slow): do it outside the lock. Only bookkeeping is locked.
        reply = self._agent.handle(
            ctx.person_id,
            ctx.space_id,
            text,
            mode,
            self._devices[ctx.space_id],
            self._energy_modes[ctx.space_id],
            self._store.new_id,
            force_intent="rest" if force_rest else None,
            wake_time=wake_time,
        )
        if reply.plan is not None:
            self._record_new_plan(reply.plan, request_epoch)
        return reply

    def create_rest_plan(
        self, ctx: RequestContext, utterance: str, mode: Optional[PlannerMode] = None, wake_time: WakeTime = "07:00"
    ) -> Plan:
        reply = self.handle_message(ctx, utterance, mode, force_rest=True, wake_time=wake_time)
        assert reply.plan is not None
        return reply.plan

    def _record_new_plan(self, plan: Plan, request_epoch: int) -> None:
        person = next(p for p in seed.PERSONS if p.person_id == plan.person_id)
        gen = plan.generation
        with self._lock:
            current_epoch = self._store.epoch(plan.space_id)
            record = PlanRecord(plan=plan, epoch=request_epoch)
            if request_epoch != current_epoch:
                plan.status = "invalidated"
            self._store.save_plan(
                record,
                events=[
                    domain_event(
                        "plan.created",
                        occurred_at=self._clock(),
                        space_id=plan.space_id,
                        aggregate_id=plan.plan_id,
                        person_id=plan.person_id,
                        scenario=plan.scenario,
                        source=plan.source,
                    )
                ],
            )
            if request_epoch != current_epoch:
                self._log(
                    plan.space_id,
                    "plan_rejected",
                    "system",
                    "生成期间服务已停止，计划已失效",
                    plan_id=plan.plan_id,
                    person_id=person.person_id,
                )
                return
            if plan.scenario == "device_command":
                self._log(
                    plan.space_id,
                    "plan_created",
                    "rule_engine",
                    f"主 Agent → 执行 Agent：{plan.summary}（{person.name}）",
                    plan_id=plan.plan_id,
                    person_id=person.person_id,
                )
            elif plan.source == "model":
                self._log(
                    plan.space_id,
                    "plan_created",
                    "experience_agent",
                    f"模型生成休息计划（{person.name}，{gen.provider}/{gen.model}，{gen.latency_ms} ms）",
                    plan_id=plan.plan_id,
                    person_id=person.person_id,
                )
            else:
                if gen.fallback_reason:
                    self._log(
                        plan.space_id,
                        "plan_fallback",
                        "system",
                        f"模型计划未采用，改用规则：{gen.fallback_reason}（{gen.latency_ms} ms）",
                        plan_id=plan.plan_id,
                        person_id=person.person_id,
                    )
                self._log(
                    plan.space_id,
                    "plan_created",
                    "rule_engine",
                    f"生成休息计划（{person.name}，{'规则降级' if gen.fallback_reason else '规则'}）",
                    plan_id=plan.plan_id,
                    person_id=person.person_id,
                )

    # ---- memory (own preference only) and energy settings ----

    def memory_view(self, ctx: RequestContext) -> MemoryView:
        self._check_context(ctx)
        with self._lock:
            return self._memory.view(ctx.person_id, ctx.space_id)

    def update_preference(self, ctx: RequestContext, preference: RestPreference) -> MemoryView:
        self._check_context(ctx)
        with self._lock:
            change = self._memory.update(ctx.person_id, preference)
            self._store.record_events(
                [
                    domain_event(
                        "memory.preference.updated",
                        occurred_at=self._clock(),
                        space_id=ctx.space_id,
                        aggregate_id=ctx.person_id,
                        person_id=ctx.person_id,
                        change=change,
                    )
                ]
            )
            person = next(p for p in seed.PERSONS if p.person_id == ctx.person_id)
            self._log(
                ctx.space_id, "memory_updated", "user", f"{person.name} 更新了自己的休息偏好：{change}", person_id=ctx.person_id
            )
            return self._memory.view(ctx.person_id, ctx.space_id)

    def set_energy_mode(self, space_id: str, ctx: RequestContext, mode: EnergyMode) -> Space:
        self._check_context(ctx)
        if ctx.space_id != space_id:
            raise ApiError("FORBIDDEN_CONTEXT", "空间与请求上下文不一致", {"spaceId": space_id})
        with self._lock:
            self._energy_modes[space_id] = mode
            self._store.record_events(
                [
                    domain_event(
                        "energy.mode.updated",
                        occurred_at=self._clock(),
                        space_id=space_id,
                        aggregate_id=space_id,
                        person_id=ctx.person_id,
                        mode=mode,
                    )
                ]
            )
            self._log(space_id, "energy_mode_changed", "user", f"节能设置改为：{'节能模式' if mode == 'eco' else '舒适优先'}")
            return self._space(next(s for s in seed.SPACES if s.space_id == space_id))

    def _reject(self, record: PlanRecord, code, message: str) -> ApiError:
        plan = record.plan
        self._log(plan.space_id, "plan_rejected", "system", message, plan_id=plan.plan_id, person_id=plan.person_id)
        return ApiError(code, message, {"planId": plan.plan_id})

    def confirm_plan(self, plan_id: str, ctx: RequestContext, plan_version: int) -> ConfirmPlanResponse:
        self._check_context(ctx)
        with self._space_lock(ctx.space_id) as space_lock:
            if space_lock.blocked:
                raise self._busy(ctx.space_id)
            return self._confirm_plan_locked(plan_id, ctx, plan_version)

    def _confirm_plan_locked(self, plan_id: str, ctx: RequestContext, plan_version: int) -> ConfirmPlanResponse:
        with self._lock:
            record = self._store.get_plan(plan_id)
            if record is None:
                raise ApiError("NOT_FOUND", "计划不存在", {"planId": plan_id})
            plan = record.plan
            if plan.space_id != ctx.space_id or plan.person_id != ctx.person_id:
                raise ApiError("FORBIDDEN_CONTEXT", "计划不属于当前人物或空间", {"planId": plan_id})
            if plan.version != plan_version:
                raise self._reject(record, "PLAN_VERSION_MISMATCH", "计划版本已变化，请刷新")

            # Idempotent: an executed (or currently executing) plan is never executed again.
            if plan.status == "executed":
                service = self._store.get_service(record.service_id) if record.service_id else None
                self._log(
                    plan.space_id,
                    "plan_confirm_repeated",
                    "system",
                    "重复确认，未再次执行",
                    service_id=service.service_id if service else None,
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
                self._store.save_plan(record)
                raise self._reject(record, "PLAN_INVALIDATED", "计划已失效（服务停止后需重新生成）")
            if plan.status == "expired" or self._clock() > plan.expires_at:
                plan.status = "expired"
                self._store.save_plan(record)
                raise self._reject(record, "PLAN_EXPIRED", "计划已过期，请重新生成")
            if plan.scenario == "device_command":
                # Direct device command: no rest service; stop/epoch still guard every write.
                plan.status = "executed"
                self._store.save_plan(record)
                self._log(
                    plan.space_id, "plan_confirmed", "user", "用户确认设备指令", plan_id=plan_id, person_id=plan.person_id
                )
                epoch_at_start = self._store.epoch(plan.space_id)
                actions = list(plan.actions)
                command_mode = True
            else:
                command_mode = False
            if not command_mode and self._store.active_service(plan.space_id):
                raise self._reject(record, "SERVICE_ALREADY_ACTIVE", "当前空间已有运行中的服务，请先停止")

            if not command_mode:
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
                    night_clock=clock_label(0),
                    night_offset_min=0,
                    # The service owns its own copy; the plan keeps the confirmed preview.
                    schedule=[step.model_copy(deep=True) for step in plan.schedule],
                    wake_time=plan.wake_time or "07:00",
                    sleep_detected_at=None,
                )
                now_utc = self._clock()
                self._store.save_service(
                    service,
                    events=[
                        domain_event(
                            "plan.confirmed",
                            occurred_at=now_utc,
                            space_id=plan.space_id,
                            aggregate_id=service.service_id,
                            person_id=plan.person_id,
                            plan_id=plan_id,
                        ),
                        domain_event(
                            "service.started",
                            occurred_at=now_utc,
                            space_id=plan.space_id,
                            aggregate_id=service.service_id,
                            person_id=plan.person_id,
                            planner_mode=service.planner_mode,
                            wake_time=service.wake_time,
                        ),
                    ],
                )
                plan.status = "executed"
                record.service_id = service.service_id
                record.results = []
                self._store.save_plan(record)
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
        if command_mode:
            self._execute_command(plan, actions, epoch_at_start)
            service = None
        else:
            self._execute(service, actions, epoch_at_start, plan_id=plan_id)

        with self._lock:
            stored = self._store.get_plan(plan_id)
            results = list(stored.results) if stored else []
            if service is not None:
                service = self._store.get_service(service.service_id) or service
            return ConfirmPlanResponse(
                plan=plan,
                service=service,
                results=results,
                device_state=self._devices[plan.space_id].read_state(),
                repeated=False,
            )

    def _execute_command(self, plan: Plan, actions: list[DeviceAction], epoch_at_start: int) -> None:
        def guard() -> Optional[str]:
            with self._lock:
                if self._store.epoch(plan.space_id) != epoch_at_start:
                    return "计划版本已失效"
                return None

        def on_result(action: DeviceAction, result: ActionResult) -> None:
            ok = result.outcome == "succeeded"
            with self._lock:
                if self._store.get_plan(plan.plan_id) is None:
                    return
                self._store.append_result(plan.plan_id, result)
                self._log(
                    plan.space_id,
                    "action_executed" if ok else "action_rejected",
                    "virtual_device" if ok else "executor",
                    f"{action.label}（回读 {result.observed_value:g}）" if ok else f"{action.label}：{result.reason}",
                    plan_id=plan.plan_id,
                    person_id=plan.person_id,
                    action=result,
                )

        Executor(self._devices[plan.space_id]).run(actions, guard, on_result)

    def _execute(
        self,
        service: Service,
        actions: list[DeviceAction],
        epoch_at_start: int,
        *,
        plan_id: Optional[str] = None,
        results: Optional[list[ActionResult]] = None,
    ) -> None:
        """Run device actions outside the lock. State is re-read from the store before every
        write, so a stop that lands meanwhile is seen no matter which store is in use."""

        def guard() -> Optional[str]:
            # Re-check under the lock right before each external write.
            with self._lock:
                current = self._store.get_service(service.service_id)
                if current is None or current.status != "active":
                    return "服务已停止"
                if self._store.epoch(service.space_id) != epoch_at_start:
                    return "计划版本已失效"
                return None

        def on_result(action: DeviceAction, result: ActionResult) -> None:
            ok = result.outcome == "succeeded"
            with self._lock:
                if results is not None:
                    results.append(result)
                if plan_id is not None:
                    self._store.append_result(plan_id, result)
                self._store.record_events(
                    [
                        domain_event(
                            "device.action.completed",
                            occurred_at=self._clock(),
                            space_id=service.space_id,
                            aggregate_id=service.service_id,
                            person_id=service.person_id,
                            device=action.device,
                            value=action.value,
                            outcome=result.outcome,
                        )
                    ]
                )
                if self._store.get_service(service.service_id) is None:
                    return
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
            if self._store.has_flag(service.service_id, FLAG_REPLANNING):
                return ignored(event_id, "上一次调整仍在进行", service)
            if self._store.has_flag(service.service_id, FLAG_ADVANCING):
                return ignored(event_id, "整晚安排正在执行，请稍后重试", service)
            if service.adjustments >= self._max_adjustments:
                return ignored(event_id, f"本次服务已调整 {service.adjustments} 次，达到上限", service)
            if service.last_adjusted_at and now - service.last_adjusted_at < self._cooldown:
                left = int((self._cooldown - (now - service.last_adjusted_at)).total_seconds()) + 1
                return ignored(event_id, f"冷却中，约 {left} 秒后才会再次调整", service)
            cached_left = self._cooldown_cache.remaining(service.service_id)
            if cached_left:
                # Redis knows about an adjustment another instance made moments ago.
                return ignored(event_id, f"冷却中，约 {cached_left} 秒后才会再次调整", service)
            self._store.acquire_flag(service.service_id, FLAG_REPLANNING)
            epoch_at_start = self._store.epoch(space_id)
            person = next(p for p in seed.PERSONS if p.person_id == service.person_id)
            mode = service.planner_mode

        try:
            # Planning (possibly a model call) happens outside the lock.
            plan, fallback_reason = self._agent.adjustment_plan(
                person.person_id, space_id, room_temp_c, mode, adapter, self._store.new_id
            )
            with self._lock:
                current = self._store.get_service(service.service_id)
                if current is None or current.status != "active" or self._store.epoch(space_id) != epoch_at_start:
                    return ignored(event_id, "规划期间服务已停止", service)
                service = current
                record = PlanRecord(plan=plan, epoch=epoch_at_start, service_id=service.service_id)
                self._store.save_plan(record)
                if fallback_reason:
                    self._log(
                        space_id,
                        "plan_fallback",
                        "system",
                        f"模型计划未采用，改用调整规则：{fallback_reason}（{plan.generation.latency_ms} ms）",
                        service_id=service.service_id,
                        plan_id=plan.plan_id,
                        person_id=person.person_id,
                    )
                if not plan.actions:
                    plan.status = "executed"
                    self._store.save_plan(record)
                    return ignored(event_id, plan.summary, service)
                plan.status = "executed"
                self._store.save_plan(record)
                service.adjustments += 1
                service.last_adjusted_at = self._clock()
                self._store.save_service(
                    service,
                    events=[
                        domain_event(
                            "service.adjusted",
                            occurred_at=self._clock(),
                            space_id=space_id,
                            aggregate_id=service.service_id,
                            person_id=service.person_id,
                            summary=plan.summary,
                            source=plan.source,
                        )
                    ],
                )
                self._cooldown_cache.start(service.service_id)
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

            self._execute(service, actions, epoch_at_start, plan_id=plan.plan_id)

            with self._lock:
                stored = self._store.get_plan(plan.plan_id)
                return EventResult(
                    event_id=event_id,
                    source="simulated",
                    outcome="adjusted",
                    reason=None,
                    service=self._store.get_service(service.service_id) or service,
                    plan=plan,
                    results=list(stored.results) if stored else [],
                    device_state=adapter.read_state(),
                )
        finally:
            with self._lock:
                self._store.release_flag(service.service_id, FLAG_REPLANNING)

    # ---- overnight schedule on a simulated clock (step 7) ----

    def advance_clock(self, service_id: str, ctx: RequestContext, minutes: Optional[int]) -> AdvanceClockResponse:
        """Move the simulated night clock and run the steps that came due.

        A step is claimed (pending -> running) under the lock before it runs, so it runs at most
        once; only one advance per service is in flight. Every write still goes through the
        executor guard (service active + space epoch), so a stop cancels the rest.
        """
        self._check_context(ctx)
        with self._space_lock(ctx.space_id) as space_lock:
            if space_lock.blocked:
                raise self._busy(ctx.space_id)
            return self._advance_clock_locked(service_id, ctx, minutes)

    def _advance_clock_locked(self, service_id: str, ctx: RequestContext, minutes: Optional[int]) -> AdvanceClockResponse:
        adapter = self._devices[ctx.space_id]
        with self._lock:
            service = self._store.get_service(service_id)
            if service is None or service.space_id != ctx.space_id:
                raise ApiError("NOT_FOUND", "服务不存在", {"serviceId": service_id})
            if service.status != "active":
                raise ApiError("SERVICE_NOT_ACTIVE", "服务已经结束", {"serviceId": service_id})
            if self._store.has_flag(service_id, FLAG_ADVANCING):
                return AdvanceClockResponse(
                    service=service, executed=[], results=[], device_state=adapter.read_state(), note="上一次推进仍在进行"
                )
            if self._store.has_flag(service_id, FLAG_REPLANNING):
                return AdvanceClockResponse(
                    service=service,
                    executed=[],
                    results=[],
                    device_state=adapter.read_state(),
                    note="环境调整正在进行，请稍后再推进",
                )
            pending = [st for st in service.schedule if st.status == "pending"]
            if not pending:
                return AdvanceClockResponse(
                    service=service, executed=[], results=[], device_state=adapter.read_state(), note="整晚安排已全部执行"
                )
            before = service.night_clock
            target = pending[0].offset_min if minutes is None else service.night_offset_min + minutes
            target = min(max(target, service.night_offset_min), service.schedule[-1].offset_min)
            service.night_offset_min = target
            service.night_clock = clock_label(target)
            due = [st for st in pending if st.offset_min <= target]
            # Claim in the store first: a step moves pending -> running exactly once, even if
            # two advances arrive together (in PostgreSQL this is one UPDATE ... RETURNING).
            claimed = set(self._store.claim_steps(service_id, [st.step_id for st in due]))
            due = [st for st in due if st.step_id in claimed]
            for st in due:
                st.status = "running"
            self._store.save_service(service)
            self._log(
                service.space_id,
                "clock_advanced",
                "simulated_clock",
                f"模拟时钟 {before} → {service.night_clock}" + (f"，到点 {len(due)} 步" if due else "，没有到点的步骤"),
                service_id=service_id,
                person_id=service.person_id,
            )
            if not due:
                return AdvanceClockResponse(
                    service=service,
                    executed=[],
                    results=[],
                    device_state=adapter.read_state(),
                    note=f"下一步在 {pending[0].at}",
                )
            self._store.acquire_flag(service_id, FLAG_ADVANCING)
            epoch_at_start = self._store.epoch(service.space_id)

        executed: list[ScheduledStep] = []
        results: list[ActionResult] = []
        try:
            for st in due:
                with self._lock:
                    current = self._store.get_service(service_id)
                    if current is None or current.status != "active":
                        st.status = "cancelled"
                        self._store.save_step(service_id, st)
                        break
                    service = current
                    self._log(
                        service.space_id,
                        "schedule_step_executed",
                        "rule_engine",
                        f"整晚安排 {st.at} {st.title}",
                        service_id=service_id,
                        person_id=service.person_id,
                    )
                step_results: list[ActionResult] = []
                self._execute(service, st.actions, epoch_at_start, results=step_results)
                with self._lock:
                    # A scheduled step is atomic at the service level: one
                    # successful device must not hide another failed device.
                    ran = self._store.get_service(service_id) is not None and (
                        not st.actions
                        or (
                            len(step_results) == len(st.actions)
                            and all(r.outcome == "succeeded" for r in step_results)
                        )
                    )
                    st.status = "done" if ran else "cancelled"
                    st.executed_at = self._clock() if ran else None
                    self._store.save_step(service_id, st)
                    results += step_results
                    executed.append(st)
        finally:
            with self._lock:
                self._store.release_flag(service_id, FLAG_ADVANCING)
                # A step that never got to run (e.g. an exception) is cancelled, never retried silently.
                for st in due:
                    if st.status == "running":
                        st.status = "cancelled"
                        self._store.save_step(service_id, st)
                skipped = [st for st in due if st.status == "cancelled"]
                stored_service = self._store.get_service(service_id)
                still_tracked = stored_service is not None
                if stored_service is not None:
                    service = stored_service.model_copy(
                        update={"night_clock": service.night_clock, "night_offset_min": service.night_offset_min}
                    )
                elif service.status == "active":
                    # A demo reset wiped the facts while this advance was in flight. The caller
                    # must not be told the service is still running.
                    service.status = "stopped"
                    service.stopped_at = self._clock()
                    for st in service.schedule:
                        if st.status in ("pending", "running"):
                            st.status = "cancelled"
                if skipped and service.status == "active" and still_tracked:
                    self._log(
                        service.space_id,
                        "schedule_cancelled",
                        "system",
                        f"设备动作未成功，{len(skipped)} 个到点步骤未完成（{skipped[0].at} 起）",
                        service_id=service_id,
                        person_id=service.person_id,
                    )
                if still_tracked and service.status == "active" and all(
                    st.status in ("done", "cancelled") for st in service.schedule
                ):
                    service.stopped_at = self._clock()
                    if any(st.status == "cancelled" for st in service.schedule):
                        service.status = "failed"
                        self._log(
                            service.space_id,
                            "service_failed",
                            "system",
                            "整晚安排执行失败，服务结束，设备保持当前状态",
                            service_id=service_id,
                            plan_id=service.plan_id,
                            person_id=service.person_id,
                        )
                    else:
                        service.status = "completed"
                        self._log(
                            service.space_id,
                            "service_completed",
                            "system",
                            f"{service.night_clock} 唤醒完成，整晚服务结束，设备保持当前状态",
                            service_id=service_id,
                            plan_id=service.plan_id,
                            person_id=service.person_id,
                        )
                if still_tracked:
                    events = []
                    if service.status in ("completed", "failed"):
                        events.append(
                            domain_event(
                                f"service.{service.status}",
                                occurred_at=self._clock(),
                                space_id=service.space_id,
                                aggregate_id=service_id,
                                person_id=service.person_id,
                                night_clock=service.night_clock,
                            )
                        )
                    self._store.save_service(service, events=events)

        with self._lock:
            return AdvanceClockResponse(
                service=self._store.get_service(service_id) or service,
                executed=executed,
                results=results,
                device_state=adapter.read_state(),
                note=None,
            )

    def simulate_sleep(self, service_id: str, ctx: RequestContext) -> AdvanceClockResponse:
        """Record an explicit demo sleep signal and run only the initial sleep step.

        It is deliberately a button/API event, not an assertion that a camera, wearable,
        or speaker has detected sleep.  Later clock steps still need explicit demo advance.
        """
        self._check_context(ctx)
        with self._lock:
            service = self._store.get_service(service_id)
            if service is None or service.space_id != ctx.space_id:
                raise ApiError("NOT_FOUND", "服务不存在", {"serviceId": service_id})
            if service.status != "active":
                raise ApiError("SERVICE_NOT_ACTIVE", "服务已经结束", {"serviceId": service_id})
            sleep_step = next((step for step in service.schedule if step.phase == "sleep"), None)
            if sleep_step is None or sleep_step.status != "pending":
                return AdvanceClockResponse(
                    service=service,
                    executed=[],
                    results=[],
                    device_state=self._devices[ctx.space_id].read_state(),
                    note="已记录模拟入睡，初始入睡步骤无需重复执行",
                )
            self._log(
                service.space_id,
                "event_received",
                "simulated_event",
                "模拟入睡信号已收到，执行入睡步骤",
                service_id=service.service_id,
                person_id=service.person_id,
            )
            minutes = max(1, sleep_step.offset_min - service.night_offset_min)

        response = self.advance_clock(service_id, ctx, minutes)
        with self._lock:
            if any(step.step_id == sleep_step.step_id and step.status == "done" for step in response.executed):
                current = self._store.get_service(service_id)
                if current is not None:
                    current.sleep_detected_at = self._clock()
                    self._store.save_service(current)
                    response.service = current
                response.note = "已模拟入睡，灯光已按计划关闭"
        return response

    def stop_service(self, service_id: str, ctx: RequestContext) -> StopServiceResponse:
        self._check_context(ctx)
        with self._lock:
            service = self._store.get_service(service_id)
            if service is None or service.space_id != ctx.space_id:
                raise ApiError("NOT_FOUND", "服务不存在", {"serviceId": service_id})
            if service.status != "active":
                raise ApiError("SERVICE_NOT_ACTIVE", "服务已经停止", {"serviceId": service_id})
            service.status = "stopped"
            service.stopped_at = self._clock()
            # Invalidate every plan created before this stop (they cannot restart the service).
            self._store.bump_epoch(service.space_id)
            self._store.invalidate_proposed_plans(service.space_id)
            pending = [st for st in service.schedule if st.status == "pending"]
            for st in pending:
                st.status = "cancelled"
            self._store.save_service(
                service,
                events=[
                    domain_event(
                        "service.stopped",
                        occurred_at=self._clock(),
                        space_id=service.space_id,
                        aggregate_id=service_id,
                        person_id=service.person_id,
                        cancelled_steps=len(pending),
                    )
                ],
            )
            self._log(
                service.space_id,
                "service_stopped",
                "user",
                "用户停止服务，设备保持当前状态",
                service_id=service_id,
                plan_id=service.plan_id,
                person_id=service.person_id,
            )
            if pending:
                self._log(
                    service.space_id,
                    "schedule_cancelled",
                    "system",
                    f"已取消 {len(pending)} 个未执行的整晚步骤（{pending[0].at} 起）",
                    service_id=service_id,
                    person_id=service.person_id,
                )
            # Default: keep devices as they are (no automatic restore).
            return StopServiceResponse(service=service, device_state=self._devices[service.space_id].read_state())

    def activity(self, account_id: str, space_id: str, limit: int) -> list[ActivityRecord]:
        self._check_space(account_id, space_id)
        with self._lock:
            return self._store.activity(space_id, limit)

    def reset(self, account_id: str) -> BootstrapResponse:
        self._check_account(account_id)
        with self._lock:
            # Give references held by in-flight requests a terminal state before
            # clearing the store. Store epochs and adapter generations below
            # prevent those requests from changing the recreated demo state.
            for space in seed.SPACES:
                active = self._store.active_service(space.space_id)
                if active is not None:
                    active.status = "stopped"
                    active.stopped_at = self._clock()
                    for step in active.schedule:
                        if step.status in ("pending", "running"):
                            step.status = "cancelled"
                    self._store.save_service(active)
            self._store.clear()
            self._memory.reset()
            self._energy_modes = {sp.space_id: sp.energy_mode for sp in seed.SPACES}
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

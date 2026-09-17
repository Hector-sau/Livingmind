// Front-end mock of the backend. Everything here is simulated and labelled "frontend_mock".
// Keep the behaviour aligned with backend/app/services/rest_service.py and the agents
// (see ./agents.ts for the mirrored rules).
import { ApiError, type LivingMindApi } from '../api';
import type {
  ActionResult,
  AdvanceClockRequest,
  AdvanceClockResponse,
  ActivityRecord,
  AgentStep,
  AssistantMessageRequest,
  AssistantReply,
  BootstrapResponse,
  ConfirmPlanRequest,
  ConfirmPlanResponse,
  ScheduledStep,
  CreateRestPlanRequest,
  DeviceAction,
  DeviceState,
  EnergyMode,
  EventResult,
  InjectEventRequest,
  MemoryView,
  OfflineEnergySimulation,
  Plan,
  PlannerMode,
  RequestContext,
  RestPreference,
  Service,
  StopServiceRequest,
  StopServiceResponse,
} from '../types';
import {
  adjustmentTarget,
  commandActions,
  energyAdvise,
  INTENT_LABEL,
  nightClockLabel,
  nightSchedule,
  parseCommand,
  precheck,
  restActions,
  routeIntent,
  TIER_LABEL,
  type Intent,
} from './agents';
import { MOCK_ACCOUNT, MOCK_INITIAL_DEVICES, MOCK_OFFLINE_ENERGY_SIMULATION, MOCK_PERSONS, MOCK_PINS, MOCK_SCENES, MOCK_SPACE_RULES, MOCK_SPACES, NIGHT_LIGHT_MAX } from './seed';

const PLAN_TTL_MS = 10 * 60 * 1000;
const EVENT_COOLDOWN_MS = 30 * 1000;
const EVENT_MAX_ADJUSTMENTS = 3;

export interface MockOptions {
  latencyMs?: number;
  now?: () => Date;
  eventCooldownMs?: number;
  /** Local hour used for the tariff (defaults to the device clock). */
  localHour?: number;
}

interface PlanRecord {
  plan: Plan;
  epoch: number;
  serviceId: string | null;
  results: ActionResult[];
}

const step = (agent: AgentStep['agent'], title: string, detail: string, ok = true): AgentStep => ({
  agent,
  title,
  detail,
  source: 'frontend_mock',
  latencyMs: 0,
  ok,
});

export function createMockApi(options: MockOptions = {}): LivingMindApi {
  const latencyMs = options.latencyMs ?? 350;
  const now = options.now ?? (() => new Date());
  const cooldownMs = options.eventCooldownMs ?? EVENT_COOLDOWN_MS;
  const localHour = () => options.localHour ?? now().getHours();
  let seq = 0;
  const id = (prefix: string) => `${prefix}-mock-${++seq}`;

  let devices: DeviceState;
  let plans: Map<string, PlanRecord>;
  let services: Map<string, Service>;
  let activity: ActivityRecord[];
  let epoch: number;
  let prefs: Map<string, RestPreference>;
  let prefUpdated: Map<string, string>;
  let energyMode: EnergyMode;

  const reset = () => {
    devices = {
      spaceId: MOCK_SPACES[0].spaceId,
      ...MOCK_INITIAL_DEVICES,
      source: 'frontend_mock',
      version: 0,
      updatedAt: now().toISOString(),
    };
    plans = new Map();
    services = new Map();
    activity = [];
    epoch = 0;
    prefs = new Map(MOCK_PERSONS.map((p) => [p.personId, { ...p.restPreference! }]));
    prefUpdated = new Map();
    energyMode = MOCK_SPACES[0].energyMode;
  };
  reset();

  // Return copies so callers cannot mutate mock state (JSON clone: Hermes-safe).
  const clone = <T>(value: T): T => JSON.parse(JSON.stringify(value)) as T;
  const delay = <T>(value: T): Promise<T> => {
    const copy = clone(value);
    return latencyMs > 0 ? new Promise((r) => setTimeout(() => r(copy), latencyMs)) : Promise.resolve(copy);
  };

  const log = (entry: Omit<ActivityRecord, 'activityId' | 'timestamp' | 'spaceId'>) => {
    activity.unshift({ activityId: id('act'), timestamp: now().toISOString(), spaceId: devices.spaceId, ...entry });
  };
  const note = (kind: ActivityRecord['kind'], message: string, extra: Partial<ActivityRecord> = {}) =>
    log({ kind, source: 'frontend_mock', message, serviceId: null, planId: null, personId: null, action: null, ...extra });

  const checkContext = (ctx: RequestContext) => {
    if (ctx.accountId !== MOCK_ACCOUNT.accountId) throw new ApiError('FORBIDDEN_CONTEXT', '演示账户不匹配', 403);
    if (!MOCK_PERSONS.some((p) => p.personId === ctx.personId))
      throw new ApiError('FORBIDDEN_CONTEXT', '该人物不属于演示账户', 403);
    if (!MOCK_SPACES.some((s) => s.spaceId === ctx.spaceId))
      throw new ApiError('FORBIDDEN_CONTEXT', '该空间不属于演示账户', 403);
    return MOCK_PERSONS.find((p) => p.personId === ctx.personId)!;
  };

  const activeService = () => [...services.values()].find((s) => s.status === 'active') ?? null;

  const bootstrap = (): BootstrapResponse => ({
    mode: 'demo',
    // The front-end mock has no model; "model" mode always degrades to a labelled rule fallback.
    planner: { defaultMode: 'rule', modelConfigured: false, provider: null, model: null, timeoutMs: 0 },
    account: MOCK_ACCOUNT,
    persons: MOCK_PERSONS.map((p) => ({ ...p, restPreference: null })),
    spaces: MOCK_SPACES.map((s) => ({ ...s, energyMode })),
    defaultSpaceId: MOCK_SPACES[0].spaceId,
    deviceState: devices,
    activeService: activeService(),
  });

  const apply = (action: DeviceAction): ActionResult => {
    if (action.command === 'set_brightness') devices.lightBrightness = action.value;
    else if (action.command === 'set_target_temperature') devices.acTargetTempC = action.value;
    else devices.curtainOpenPercent = action.value;
    devices.version += 1;
    devices.updatedAt = now().toISOString();
    return { actionId: action.actionId, device: action.device, command: action.command, value: action.value, outcome: 'succeeded', reason: null, observedValue: action.value };
  };

  const memoryView = (personId: string): MemoryView => {
    const person = MOCK_PERSONS.find((p) => p.personId === personId)!;
    return {
      personId,
      isGuest: person.isGuest,
      preference: prefs.get(personId)!,
      editable: !person.isGuest,
      updatedAt: prefUpdated.get(personId) ?? null,
      sharedRules: MOCK_SPACE_RULES,
    };
  };

  const newPlan = (partial: Omit<Plan, 'planId' | 'version' | 'status' | 'createdAt' | 'expiresAt'>): Plan => {
    const created = now();
    return {
      planId: id('plan'),
      version: 1,
      status: 'proposed',
      createdAt: created.toISOString(),
      expiresAt: new Date(created.getTime() + PLAN_TTL_MS).toISOString(),
      ...partial,
    };
  };

  const record = (plan: Plan) => {
    plans.set(plan.planId, { plan, epoch, serviceId: null, results: [] });
  };

  const handle = (req: AssistantMessageRequest, force?: Intent): AssistantReply => {
    const person = checkContext(req.context);
    const mode: PlannerMode = req.mode ?? 'rule';
    const intent = force ?? routeIntent(req.text);
    const trace: AgentStep[] = [step('orchestrator', `识别意图：${INTENT_LABEL[intent]}`, '前端模拟的规则路由')];

    if (intent === 'rest') {
      const pref = prefs.get(person.personId)!;
      trace.push(
        step('memory', '读取上下文', `${person.isGuest ? '访客（空间默认设置）' : `${person.name} 的休息偏好（仅本人）`} + 空间规则 ${MOCK_SPACE_RULES.length} 条`),
      );
      const wantsModel = mode === 'model';
      const fallbackReason = wantsModel ? '前端模拟模式没有模型，改用本地规则' : null;
      trace.push(
        step('experience', '生成体验目标', `体验目标：灯光 ${pref.lightBrightness}% · 空调 ${pref.acTargetTempC}°C · 窗帘 ${pref.curtainOpenPercent}%${fallbackReason ? `；${fallbackReason}` : ''}`, !wantsModel),
      );
      const advice = energyAdvise(pref, energyMode, localHour());
      const target = advice.applied ? { ...pref, acTargetTempC: advice.recommendedAcC } : pref;
      trace.push(
        step(
          'energy',
          '能源策略',
          `${energyMode === 'eco' ? '节能模式' : '舒适优先'} · ${advice.tariff === 'peak' ? '高峰' : '非高峰'}电价 · 建议 ${advice.recommendedAcC}°C${advice.applied ? ' · 已应用' : ' · 未改设定'} · 估算负荷 ${advice.loadKwBefore}→${advice.loadKwAfter} kW（${TIER_LABEL[advice.tierAfter]}档）`,
        ),
      );
      const built = restActions(target, id, NIGHT_LIGHT_MAX);
      const schedule = nightSchedule(target, pref, NIGHT_LIGHT_MAX, id);
      trace.push(step('space_execution', '生成设备动作', `生成 ${built.actions.length} 个动作 · 整晚安排 ${schedule.length} 个定时步骤`));
      const checked = precheck(built.actions);
      trace.push(step('harness', '执行前检查', `${checked.problems.length ? checked.problems.join('；') : '全部通过白名单与参数范围'} · 计划与整晚安排需用户确认后执行`, !checked.problems.length));
      const notes = [
        ...(person.isGuest ? ['访客模式：使用空间默认设置，没有读取任何个人偏好'] : []),
        wantsModel ? `前端模拟：${fallbackReason}` : '前端模拟：计划由本地规则生成，没有调用后端或模型',
        '当前为固定休息场景，输入文字只做记录，不做语义理解',
        ...built.notes,
        ...(advice.applied ? [`节能模式：空调由 ${advice.requestedAcC}°C 调到 ${advice.recommendedAcC}°C（仍在舒适范围内）`] : []),
        `整晚安排（模拟时钟，随计划一起确认）：${schedule[0].at} 起共 ${schedule.length} 步，${schedule[schedule.length - 1].at} 唤醒完成后服务结束`,
      ];
      const plan = newPlan({
        personId: person.personId,
        spaceId: req.context.spaceId,
        scenario: 'rest',
        source: 'frontend_mock',
        summary: person.isGuest ? '按空间默认设置调整灯光、空调和窗帘（访客）' : `按 ${person.name} 的休息偏好调整灯光、空调和窗帘`,
        notes,
        utterance: req.text,
        actions: checked.allowed,
        generation: { modeRequested: mode, provider: null, model: null, latencyMs: 0, fallbackReason, goal: null },
        trace,
        energy: advice,
        schedule,
      });
      record(plan);
      if (fallbackReason) note('plan_fallback', fallbackReason, { planId: plan.planId, personId: person.personId });
      note('plan_created', `生成休息计划（${person.name}）`, { planId: plan.planId, personId: person.personId });
      return { kind: 'plan', intent, text: plan.summary, plan, trace };
    }

    if (intent === 'device_command') {
      const target = parseCommand(req.text, NIGHT_LIGHT_MAX);
      if (target.light === null && target.ac === null && target.curtain === null) {
        trace.push(step('space_execution', '解析设备指令', '没有识别出设备和目标值', false));
        return { kind: 'answer', intent, text: '我没听清要调哪个设备，可以说“把灯关了”“空调调到 24 度”或“打开窗帘”。', plan: null, trace };
      }
      const built = commandActions(target, devices, id);
      trace.push(step('space_execution', '解析设备指令', `${target.phrases.join('、')} → ${built.actions.length} 个动作`));
      const checked = precheck(built.actions);
      trace.push(step('harness', '执行前检查', `${checked.problems.length ? `拦截：${checked.problems.join('；')}` : '通过白名单与参数范围'} · 需用户确认后执行`, !checked.problems.length));
      if (checked.allowed.length === 0) {
        const why = [...checked.problems, ...built.notes].join('；') || '没有需要执行的动作';
        return { kind: 'answer', intent, text: `没有生成动作：${why}`, plan: null, trace };
      }
      const summary = `设备指令：${checked.allowed.map((a) => a.label).join('，')}`;
      const plan = newPlan({
        personId: person.personId,
        spaceId: req.context.spaceId,
        scenario: 'device_command',
        source: 'frontend_mock',
        summary,
        notes: ['简化分支：直接设备指令，不经过体验 Agent 与能源模块', ...built.notes],
        utterance: req.text,
        actions: checked.allowed,
        generation: { modeRequested: mode, provider: null, model: null, latencyMs: 0, fallbackReason: null, goal: null },
        trace,
        energy: null,
        schedule: [],
      });
      record(plan);
      note('plan_created', `主 Agent → 执行 Agent：${summary}（${person.name}）`, { planId: plan.planId, personId: person.personId });
      return { kind: 'plan', intent, text: summary, plan, trace };
    }

    if (intent === 'status') {
      trace.push(step('space_execution', '读取设备状态', '只读，不生成动作'));
      return {
        kind: 'answer',
        intent,
        text: `卧室现在：灯光 ${devices.lightBrightness}%，空调设定 ${devices.acTargetTempC}°C，窗帘开度 ${devices.curtainOpenPercent}%（前端模拟设备）。`,
        plan: null,
        trace,
      };
    }
    return { kind: 'answer', intent, text: '我目前负责休息相关的空间服务：可以说“我想休息”，或者直接说“把灯关了”“空调调到 24 度”。', plan: null, trace };
  };

  return {
    mode: 'mock',

    async bootstrap() {
      return delay(bootstrap());
    },

    async unlockPerson(personId: string, pin: string | null) {
      if (!MOCK_PERSONS.some((p) => p.personId === personId)) throw new ApiError('NOT_FOUND', '人物不存在', 404);
      const expected = MOCK_PINS[personId];
      if (expected !== undefined && pin !== expected) throw new ApiError('PIN_INVALID', 'PIN 不正确', 403);
      return delay({ personId, unlocked: true, note: '演示用 PIN，仅防止共享平板上误切换，不是登录认证' });
    },

    async getScenes() {
      return delay({ items: MOCK_SCENES });
    },

    async getDeviceState() {
      return delay(devices);
    },

    async sendMessage(req: AssistantMessageRequest) {
      return delay(handle(req));
    },

    async createRestPlan(req: CreateRestPlanRequest) {
      return delay(handle({ context: req.context, text: req.utterance, mode: req.mode }, 'rest').plan!);
    },

    async getMemory(ctx: RequestContext) {
      checkContext(ctx);
      return delay(memoryView(ctx.personId));
    },

    async updatePreference(ctx: RequestContext, preference: RestPreference) {
      const person = checkContext(ctx);
      if (person.isGuest) throw new ApiError('NOT_EDITABLE', '访客没有个人偏好，不能编辑', 409);
      if (preference.lightBrightness > NIGHT_LIGHT_MAX)
        throw new ApiError('VALIDATION_ERROR', `休息偏好的灯光不能超过 ${NIGHT_LIGHT_MAX}%（空间规则）`, 422);
      if (preference.acTargetTempC < 16 || preference.acTargetTempC > 30) throw new ApiError('VALIDATION_ERROR', '空调温度超出范围', 422);
      prefs.set(person.personId, { ...preference });
      prefUpdated.set(person.personId, now().toISOString());
      note('memory_updated', `${person.name} 更新了自己的休息偏好（前端模拟）`, { personId: person.personId });
      return delay(memoryView(person.personId));
    },

    async setEnergyMode(ctx: RequestContext, mode: EnergyMode) {
      checkContext(ctx);
      energyMode = mode;
      note('energy_mode_changed', `节能设置改为：${mode === 'eco' ? '节能模式' : '舒适优先'}（前端模拟）`);
      return delay({ ...MOCK_SPACES[0], energyMode });
    },

    async getOfflineEnergySimulation(spaceId: string): Promise<OfflineEnergySimulation> {
      if (spaceId !== MOCK_SPACES[0].spaceId) throw new ApiError('FORBIDDEN_CONTEXT', '该空间不属于演示账户', 403);
      return delay(MOCK_OFFLINE_ENERGY_SIMULATION);
    },

    async confirmPlan(planId: string, req: ConfirmPlanRequest): Promise<ConfirmPlanResponse> {
      checkContext(req.context);
      const rec = plans.get(planId);
      if (!rec) throw new ApiError('NOT_FOUND', '计划不存在', 404);
      const { plan } = rec;
      if (plan.personId !== req.context.personId) throw new ApiError('FORBIDDEN_CONTEXT', '计划不属于当前人物', 403);
      if (plan.version !== req.planVersion) throw new ApiError('PLAN_VERSION_MISMATCH', '计划版本已变化，请刷新', 409);

      if (plan.status === 'executed') {
        const service = rec.serviceId ? services.get(rec.serviceId)! : null;
        note('plan_confirm_repeated', '重复确认，未再次执行', { serviceId: rec.serviceId, planId, personId: plan.personId });
        return delay({ plan, service, results: rec.results, deviceState: devices, repeated: true });
      }
      if (plan.status !== 'proposed' || rec.epoch !== epoch) {
        plan.status = 'invalidated';
        throw new ApiError('PLAN_INVALIDATED', '计划已失效（服务停止后需重新生成）', 409);
      }
      if (now().getTime() > Date.parse(plan.expiresAt)) {
        plan.status = 'expired';
        throw new ApiError('PLAN_EXPIRED', '计划已过期，请重新生成', 409);
      }

      let service: Service | null = null;
      if (plan.scenario !== 'device_command') {
        if (activeService()) throw new ApiError('SERVICE_ALREADY_ACTIVE', '当前空间已有运行中的服务，请先停止', 409);
        service = {
          serviceId: id('svc'),
          spaceId: plan.spaceId,
          personId: plan.personId,
          planId,
          planVersion: plan.version,
          status: 'active',
          startedAt: now().toISOString(),
          stoppedAt: null,
          plannerMode: plan.generation.modeRequested,
          adjustments: 0,
          lastAdjustedAt: null,
          nightClock: nightClockLabel(0),
          nightOffsetMin: 0,
          schedule: plan.schedule.map((s) => ({ ...s, actions: s.actions.map((a) => ({ ...a })) })),
        };
        services.set(service.serviceId, service);
        rec.serviceId = service.serviceId;
      }
      plan.status = 'executed';
      log({
        kind: 'plan_confirmed',
        source: 'user',
        message: service ? '用户确认执行休息计划' : '用户确认设备指令',
        serviceId: service?.serviceId ?? null,
        planId,
        personId: plan.personId,
        action: null,
      });
      rec.results = plan.actions.map((a) => {
        const r = apply(a);
        note('action_executed', a.label, { serviceId: service?.serviceId ?? null, planId, personId: plan.personId, action: r });
        return r;
      });
      return delay({ plan, service, results: rec.results, deviceState: devices, repeated: false });
    },

    async stopService(serviceId: string, req: StopServiceRequest): Promise<StopServiceResponse> {
      checkContext(req.context);
      const service = services.get(serviceId);
      if (!service) throw new ApiError('NOT_FOUND', '服务不存在', 404);
      if (service.status !== 'active') throw new ApiError('SERVICE_NOT_ACTIVE', '服务已经停止', 409);
      service.status = 'stopped';
      service.stoppedAt = now().toISOString();
      epoch += 1;
      log({ kind: 'service_stopped', source: 'user', message: '用户停止服务，设备保持当前状态', serviceId, planId: service.planId, personId: service.personId, action: null });
      const pending = service.schedule.filter((s) => s.status === 'pending');
      pending.forEach((s) => (s.status = 'cancelled'));
      if (pending.length) note('schedule_cancelled', `已取消 ${pending.length} 个未执行的整晚步骤（${pending[0].at} 起）`, { serviceId, personId: service.personId });
      return delay({ service, deviceState: devices });
    },

    async advanceClock(serviceId: string, req: AdvanceClockRequest): Promise<AdvanceClockResponse> {
      checkContext(req.context);
      const service = services.get(serviceId);
      if (!service) throw new ApiError('NOT_FOUND', '服务不存在', 404);
      if (service.status !== 'active') throw new ApiError('SERVICE_NOT_ACTIVE', '服务已经结束', 409);
      const pending = service.schedule.filter((s) => s.status === 'pending');
      const reply = (executed: ScheduledStep[], results: ActionResult[], why: string | null) =>
        delay({ service, executed, results, deviceState: devices, note: why });
      if (pending.length === 0) return reply([], [], '整晚安排已全部执行');
      const before = service.nightClock;
      const last = service.schedule[service.schedule.length - 1].offsetMin;
      const wanted = req.minutes == null ? pending[0].offsetMin : service.nightOffsetMin + req.minutes;
      const target = Math.min(Math.max(wanted, service.nightOffsetMin), last);
      service.nightOffsetMin = target;
      service.nightClock = nightClockLabel(target);
      const due = pending.filter((s) => s.offsetMin <= target);
      due.forEach((s) => (s.status = 'running'));
      log({
        kind: 'clock_advanced',
        source: 'frontend_mock',
        message: `模拟时钟 ${before} → ${service.nightClock}${due.length ? `，到点 ${due.length} 步` : '，没有到点的步骤'}（前端模拟）`,
        serviceId,
        planId: null,
        personId: service.personId,
        action: null,
      });
      if (due.length === 0) return reply([], [], `下一步在 ${pending[0].at}`);
      const results: ActionResult[] = [];
      for (const s of due) {
        note('schedule_step_executed', `整晚安排 ${s.at} ${s.title}（前端模拟）`, { serviceId, personId: service.personId });
        for (const a of s.actions) {
          const r = apply(a);
          note('action_executed', a.label, { serviceId, personId: service.personId, action: r });
          results.push(r);
        }
        s.status = 'done';
        s.executedAt = now().toISOString();
      }
      if (service.schedule.every((s) => s.status === 'done' || s.status === 'cancelled')) {
        service.status = 'completed';
        service.stoppedAt = now().toISOString();
        note('service_completed', `${service.nightClock} 唤醒完成，整晚服务结束，设备保持当前状态（前端模拟）`, {
          serviceId,
          planId: service.planId,
          personId: service.personId,
        });
      }
      return reply(due, results, null);
    },

    async injectEvent(_spaceId: string, req: InjectEventRequest): Promise<EventResult> {
      checkContext(req.context);
      const eventId = id('event');
      const service = activeService();
      note('event_received', `模拟事件：室温变为 ${req.roomTempC}°C（前端模拟）`, { serviceId: service?.serviceId ?? null });
      const ignore = (reason: string): Promise<EventResult> => {
        note('event_ignored', `事件已忽略：${reason}`, { serviceId: service?.serviceId ?? null, personId: service?.personId ?? null });
        return delay({ eventId, source: 'simulated', outcome: 'ignored', reason, service, plan: null, results: [], deviceState: devices });
      };
      if (!service) return ignore('当前没有运行中的服务');
      if (service.adjustments >= EVENT_MAX_ADJUSTMENTS) return ignore(`本次服务已调整 ${service.adjustments} 次，达到上限`);
      if (service.lastAdjustedAt && now().getTime() - Date.parse(service.lastAdjustedAt) < cooldownMs) {
        const left = Math.ceil((cooldownMs - (now().getTime() - Date.parse(service.lastAdjustedAt))) / 1000);
        return ignore(`冷却中，约 ${left} 秒后才会再次调整`);
      }
      const person = MOCK_PERSONS.find((p) => p.personId === service.personId)!;
      const { next, summary } = adjustmentTarget(prefs.get(person.personId)!.acTargetTempC, devices.acTargetTempC, req.roomTempC);
      if (next === devices.acTargetTempC) return ignore(summary);
      const wantsModel = service.plannerMode === 'model';
      const action: DeviceAction = { actionId: id('a'), device: 'ac', command: 'set_target_temperature', value: next, label: `空调设定 ${next}°C` };
      const plan: Plan = {
        ...newPlan({
          personId: person.personId,
          spaceId: devices.spaceId,
          scenario: 'rest_adjustment',
          source: 'frontend_mock',
          summary,
          notes: [wantsModel ? '前端模拟：前端模拟模式没有模型，改用本地调整规则' : '前端模拟：本地调整规则'],
          utterance: `【模拟事件】室温 ${req.roomTempC}°C`,
          actions: [action],
          generation: {
            modeRequested: service.plannerMode,
            provider: null,
            model: null,
            latencyMs: 0,
            fallbackReason: wantsModel ? '前端模拟模式没有模型，改用本地规则' : null,
            goal: null,
          },
          trace: [
            step('orchestrator', '处理模拟事件', `室温 ${req.roomTempC}°C · 读取${person.name}的偏好`),
            step('experience', '调整目标', summary),
            step('energy', '能源策略', '事件调整以舒适优先，不应用节能策略'),
            step('space_execution', '生成调整动作', '只对有变化的设备生成 1 个动作'),
            step('harness', '执行前检查', '通过'),
          ],
          energy: null,
          schedule: [],
        }),
        status: 'executed',
      };
      plans.set(plan.planId, { plan, epoch, serviceId: service.serviceId, results: [] });
      service.adjustments += 1;
      service.lastAdjustedAt = now().toISOString();
      note('service_adjusted', `自动调整（前端模拟）：${summary}`, { serviceId: service.serviceId, planId: plan.planId, personId: person.personId });
      const result = apply(action);
      note('action_executed', action.label, { serviceId: service.serviceId, planId: plan.planId, personId: person.personId, action: result });
      return delay({ eventId, source: 'simulated', outcome: 'adjusted', reason: null, service, plan, results: [result], deviceState: devices });
    },

    async getActivity(_spaceId: string, limit = 50) {
      return delay({ items: activity.slice(0, limit) });
    },

    async resetDemo() {
      reset();
      note('demo_reset', '演示数据已重置（前端模拟）');
      return delay(bootstrap());
    },
  };
}

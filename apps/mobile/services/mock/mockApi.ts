// Front-end mock of the backend rules. Everything here is simulated and labelled "frontend_mock".
// Keep the behaviour aligned with backend/app/services/rest_service.py.
import { ApiError, type LivingMindApi } from '../api';
import type {
  ActionResult,
  ActivityRecord,
  BootstrapResponse,
  ConfirmPlanRequest,
  ConfirmPlanResponse,
  CreateRestPlanRequest,
  DeviceAction,
  DeviceState,
  EventResult,
  InjectEventRequest,
  Plan,
  RequestContext,
  Service,
  StopServiceRequest,
  StopServiceResponse,
} from '../types';
import { MOCK_ACCOUNT, MOCK_INITIAL_DEVICES, MOCK_PERSONS, MOCK_SPACES } from './seed';

const PLAN_TTL_MS = 10 * 60 * 1000;
// Mirrors backend config defaults and backend/app/rules/rest_rule.py adjustment_rule.
const EVENT_COOLDOWN_MS = 30 * 1000;
const EVENT_MAX_ADJUSTMENTS = 3;
const ADJUST_TRIGGER_C = 2;
const ADJUST_STEP_C = 1;
const ADJUST_BAND_C = 3;

export interface MockOptions {
  latencyMs?: number;
  now?: () => Date;
  eventCooldownMs?: number;
}

interface PlanRecord {
  plan: Plan;
  epoch: number;
}

export function createMockApi(options: MockOptions = {}): LivingMindApi {
  const latencyMs = options.latencyMs ?? 350;
  const now = options.now ?? (() => new Date());
  const cooldownMs = options.eventCooldownMs ?? EVENT_COOLDOWN_MS;
  let seq = 0;
  const id = (prefix: string) => `${prefix}-mock-${++seq}`;

  let devices: DeviceState;
  let plans: Map<string, PlanRecord>;
  let services: Map<string, Service>;
  let activity: ActivityRecord[];
  let epoch: number;
  let confirmResults: Map<string, ActionResult[]>;

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
    confirmResults = new Map();
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

  const checkContext = (ctx: RequestContext) => {
    if (ctx.accountId !== MOCK_ACCOUNT.accountId) throw new ApiError('FORBIDDEN_CONTEXT', '演示账户不匹配', 403);
    if (!MOCK_PERSONS.some((p) => p.personId === ctx.personId))
      throw new ApiError('FORBIDDEN_CONTEXT', '该人物不属于演示账户', 403);
    if (!MOCK_SPACES.some((s) => s.spaceId === ctx.spaceId))
      throw new ApiError('FORBIDDEN_CONTEXT', '该空间不属于演示账户', 403);
  };

  const activeService = () => [...services.values()].find((s) => s.status === 'active') ?? null;

  const bootstrap = (): BootstrapResponse => ({
    mode: 'demo',
    // The front-end mock has no model; "model" mode always degrades to a labelled rule fallback.
    planner: { defaultMode: 'rule', modelConfigured: false, provider: null, model: null, timeoutMs: 0 },
    account: MOCK_ACCOUNT,
    persons: MOCK_PERSONS,
    spaces: MOCK_SPACES,
    defaultSpaceId: MOCK_SPACES[0].spaceId,
    deviceState: devices,
    activeService: activeService(),
  });

  const apply = (action: DeviceAction): ActionResult => {
    const base = { actionId: action.actionId, device: action.device, command: action.command, value: action.value };
    if (action.command === 'set_brightness') devices.lightBrightness = action.value;
    else if (action.command === 'set_target_temperature') devices.acTargetTempC = action.value;
    else devices.curtainOpenPercent = action.value;
    devices.version += 1;
    devices.updatedAt = now().toISOString();
    return { ...base, outcome: 'succeeded', reason: null, observedValue: action.value };
  };

  return {
    mode: 'mock',

    async bootstrap() {
      return delay(bootstrap());
    },

    async getDeviceState() {
      return delay(devices);
    },

    async createRestPlan(req: CreateRestPlanRequest) {
      checkContext(req.context);
      const person = MOCK_PERSONS.find((p) => p.personId === req.context.personId)!;
      const pref = person.restPreference;
      const created = now();
      const actions: DeviceAction[] = [
        { actionId: id('a'), device: 'light', command: 'set_brightness', value: pref.lightBrightness, label: `灯光亮度调到 ${pref.lightBrightness}%` },
        { actionId: id('a'), device: 'ac', command: 'set_target_temperature', value: pref.acTargetTempC, label: `空调设定 ${pref.acTargetTempC}°C` },
        { actionId: id('a'), device: 'curtain', command: 'set_open_percent', value: pref.curtainOpenPercent, label: pref.curtainOpenPercent === 0 ? '窗帘全部关闭' : `窗帘保留 ${pref.curtainOpenPercent}%` },
      ];
      const wantsModel = req.mode === 'model';
      const fallbackReason = wantsModel ? '前端模拟模式没有模型，改用本地规则' : null;
      const plan: Plan = {
        planId: id('plan'),
        version: 1,
        personId: person.personId,
        spaceId: req.context.spaceId,
        scenario: 'rest',
        source: 'frontend_mock',
        summary: `按 ${person.name} 的休息偏好调整灯光、空调和窗帘`,
        notes: [
          wantsModel ? `前端模拟：${fallbackReason}` : '前端模拟：计划由本地规则生成，没有调用后端或模型',
          '当前为固定休息场景，输入文字只做记录，不做语义理解',
        ],
        generation: {
          modeRequested: wantsModel ? 'model' : 'rule',
          provider: null,
          model: null,
          latencyMs: 0,
          fallbackReason,
          goal: null,
        },
        utterance: req.utterance,
        actions,
        status: 'proposed',
        createdAt: created.toISOString(),
        expiresAt: new Date(created.getTime() + PLAN_TTL_MS).toISOString(),
      };
      plans.set(plan.planId, { plan, epoch });
      if (fallbackReason) {
        log({ kind: 'plan_fallback', source: 'frontend_mock', message: fallbackReason, serviceId: null, planId: plan.planId, personId: person.personId, action: null });
      }
      log({ kind: 'plan_created', source: 'frontend_mock', message: `生成休息计划（${person.name}）`, serviceId: null, planId: plan.planId, personId: person.personId, action: null });
      return delay(plan);
    },

    async confirmPlan(planId: string, req: ConfirmPlanRequest): Promise<ConfirmPlanResponse> {
      checkContext(req.context);
      const record = plans.get(planId);
      if (!record) throw new ApiError('NOT_FOUND', '计划不存在', 404);
      const { plan } = record;
      if (plan.personId !== req.context.personId) throw new ApiError('FORBIDDEN_CONTEXT', '计划不属于当前人物', 403);
      if (plan.version !== req.planVersion) throw new ApiError('PLAN_VERSION_MISMATCH', '计划版本已变化，请刷新', 409);

      if (plan.status === 'executed') {
        const service = [...services.values()].find((s) => s.planId === planId)!;
        log({ kind: 'plan_confirm_repeated', source: 'frontend_mock', message: '重复确认，未再次执行', serviceId: service.serviceId, planId, personId: plan.personId, action: null });
        return delay({ plan, service, results: confirmResults.get(planId) ?? [], deviceState: devices, repeated: true });
      }
      if (plan.status !== 'proposed' || record.epoch !== epoch) {
        plan.status = 'invalidated';
        throw new ApiError('PLAN_INVALIDATED', '计划已失效（服务停止后需重新生成）', 409);
      }
      if (now().getTime() > Date.parse(plan.expiresAt)) {
        plan.status = 'expired';
        throw new ApiError('PLAN_EXPIRED', '计划已过期，请重新生成', 409);
      }
      if (activeService()) throw new ApiError('SERVICE_ALREADY_ACTIVE', '当前空间已有运行中的服务，请先停止', 409);

      const service: Service = {
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
      };
      services.set(service.serviceId, service);
      plan.status = 'executed';
      log({ kind: 'plan_confirmed', source: 'user', message: '用户确认执行休息计划', serviceId: service.serviceId, planId, personId: plan.personId, action: null });
      const results = plan.actions.map((a) => {
        const r = apply(a);
        log({ kind: 'action_executed', source: 'frontend_mock', message: a.label, serviceId: service.serviceId, planId, personId: plan.personId, action: r });
        return r;
      });
      confirmResults.set(planId, results);
      return delay({ plan, service, results, deviceState: devices, repeated: false });
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
      return delay({ service, deviceState: devices });
    },

    async injectEvent(_spaceId: string, req: InjectEventRequest): Promise<EventResult> {
      checkContext(req.context);
      const eventId = id('event');
      const service = activeService();
      log({ kind: 'event_received', source: 'frontend_mock', message: `模拟事件：室温变为 ${req.roomTempC}°C（前端模拟）`, serviceId: service?.serviceId ?? null, planId: null, personId: null, action: null });
      const ignore = (reason: string): Promise<EventResult> => {
        log({ kind: 'event_ignored', source: 'frontend_mock', message: `事件已忽略：${reason}`, serviceId: service?.serviceId ?? null, planId: null, personId: service?.personId ?? null, action: null });
        return delay({ eventId, source: 'simulated', outcome: 'ignored', reason, service, plan: null, results: [], deviceState: devices });
      };
      if (!service) return ignore('当前没有运行中的服务');
      if (service.adjustments >= EVENT_MAX_ADJUSTMENTS) return ignore(`本次服务已调整 ${service.adjustments} 次，达到上限`);
      if (service.lastAdjustedAt && now().getTime() - Date.parse(service.lastAdjustedAt) < cooldownMs) {
        const left = Math.ceil((cooldownMs - (now().getTime() - Date.parse(service.lastAdjustedAt))) / 1000);
        return ignore(`冷却中，约 ${left} 秒后才会再次调整`);
      }
      const person = MOCK_PERSONS.find((p) => p.personId === service.personId)!;
      const pref = person.restPreference.acTargetTempC;
      const target = devices.acTargetTempC;
      let next = target;
      if (req.roomTempC >= target + ADJUST_TRIGGER_C) next = Math.max(target - ADJUST_STEP_C, pref - ADJUST_BAND_C, 16);
      else if (req.roomTempC <= target - ADJUST_TRIGGER_C) next = Math.min(target + ADJUST_STEP_C, pref + ADJUST_BAND_C, 30);
      if (next === target) return ignore(Math.abs(req.roomTempC - target) < ADJUST_TRIGGER_C ? `室温 ${req.roomTempC}°C 与设定 ${target}°C 接近，无需调整` : '已到偏好允许的调整边界');
      const wantsModel = service.plannerMode === 'model';
      const created = now();
      const action: DeviceAction = { actionId: id('a'), device: 'ac', command: 'set_target_temperature', value: next, label: `空调设定 ${next}°C` };
      const plan: Plan = {
        planId: id('plan'),
        version: 1,
        personId: person.personId,
        spaceId: devices.spaceId,
        scenario: 'rest_adjustment',
        source: 'frontend_mock',
        summary: `室温 ${req.roomTempC}°C，空调调整到 ${next}°C`,
        notes: [wantsModel ? '前端模拟：前端模拟模式没有模型，改用本地调整规则' : '前端模拟：本地调整规则'],
        utterance: `【模拟事件】室温 ${req.roomTempC}°C`,
        actions: [action],
        status: 'executed',
        createdAt: created.toISOString(),
        expiresAt: new Date(created.getTime() + PLAN_TTL_MS).toISOString(),
        generation: {
          modeRequested: service.plannerMode,
          provider: null,
          model: null,
          latencyMs: 0,
          fallbackReason: wantsModel ? '前端模拟模式没有模型，改用本地规则' : null,
          goal: null,
        },
      };
      plans.set(plan.planId, { plan, epoch });
      service.adjustments += 1;
      service.lastAdjustedAt = created.toISOString();
      log({ kind: 'service_adjusted', source: 'frontend_mock', message: `自动调整（前端模拟）：${plan.summary}`, serviceId: service.serviceId, planId: plan.planId, personId: person.personId, action: null });
      const result = apply(action);
      log({ kind: 'action_executed', source: 'frontend_mock', message: action.label, serviceId: service.serviceId, planId: plan.planId, personId: person.personId, action: result });
      return delay({ eventId, source: 'simulated', outcome: 'adjusted', reason: null, service, plan, results: [result], deviceState: devices });
    },

    async getActivity(_spaceId: string, limit = 50) {
      return delay({ items: activity.slice(0, limit) });
    },

    async resetDemo() {
      reset();
      log({ kind: 'demo_reset', source: 'frontend_mock', message: '演示数据已重置（前端模拟）', serviceId: null, planId: null, personId: null, action: null });
      return delay(bootstrap());
    },
  };
}

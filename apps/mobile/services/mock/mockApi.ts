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
  Plan,
  RequestContext,
  Service,
  StopServiceRequest,
  StopServiceResponse,
} from '../types';
import { MOCK_ACCOUNT, MOCK_INITIAL_DEVICES, MOCK_PERSONS, MOCK_SPACES } from './seed';

const PLAN_TTL_MS = 10 * 60 * 1000;

export interface MockOptions {
  latencyMs?: number;
  now?: () => Date;
}

interface PlanRecord {
  plan: Plan;
  epoch: number;
}

export function createMockApi(options: MockOptions = {}): LivingMindApi {
  const latencyMs = options.latencyMs ?? 350;
  const now = options.now ?? (() => new Date());
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
      const plan: Plan = {
        planId: id('plan'),
        version: 1,
        personId: person.personId,
        spaceId: req.context.spaceId,
        scenario: 'rest',
        source: 'frontend_mock',
        summary: `按 ${person.name} 的休息偏好调整灯光、空调和窗帘`,
        notes: ['前端模拟：计划由本地规则生成，没有调用后端或模型', '当前为固定休息场景，输入文字只做记录，不做语义理解'],
        utterance: req.utterance,
        actions,
        status: 'proposed',
        createdAt: created.toISOString(),
        expiresAt: new Date(created.getTime() + PLAN_TTL_MS).toISOString(),
      };
      plans.set(plan.planId, { plan, epoch });
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

    async getActivity(_spaceId: string, limit = 50) {
      return delay({ items: activity.slice(0, limit) });
    },

    async resetDemo() {
      reset();
      return delay(bootstrap());
    },
  };
}

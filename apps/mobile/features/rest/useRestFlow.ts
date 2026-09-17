import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { ApiError, DEMO_ACCOUNT_ID, type LivingMindApi } from '../../services';
import type {
  ActionResult,
  ActivityRecord,
  AssistantReply,
  BootstrapResponse,
  EnergyMode,
  MemoryView,
  OfflineEnergySimulation,
  RestPreference,
  ConfirmPlanResponse,
  DeviceState,
  EventResult,
  AdvanceClockResponse,
  Plan,
  PlannerMode,
  RequestContext,
  Scene,
  Service,
  StopServiceResponse,
} from '../../services/types';
import { planBlockReason } from './planGate';

export type Busy = null | 'plan' | 'confirm' | 'stop' | 'refresh' | 'reset' | 'event' | 'unlock' | 'memory' | 'energy' | 'clock';

export interface FlowError {
  message: string;
  connectivity: boolean;
  code: string | null;
}

export type Outcome<T> = { ok: true; value: T } | { ok: false; error: FlowError };

export interface RestFlowState {
  phase: 'loading' | 'error' | 'ready';
  data: BootstrapResponse | null;
  scenes: Scene[];
  personId: string | null;
  /** Current person's own memory (preference + shared rules). */
  memory: MemoryView | null;
  mode: PlannerMode;
  plan: Plan | null;
  service: Service | null;
  results: ActionResult[];
  deviceState: DeviceState | null;
  deviceStale: boolean;
  activity: ActivityRecord[];
  /** Supplied fixed-day evidence, separate from the online energy-rule plan advice. */
  energySimulation: OfflineEnergySimulation | null;
  busy: Busy;
  error: FlowError | null;
  info: string | null;
}

const initial: RestFlowState = {
  phase: 'loading',
  data: null,
  scenes: [],
  personId: null,
  memory: null,
  mode: 'rule',
  plan: null,
  service: null,
  results: [],
  deviceState: null,
  deviceStale: false,
  activity: [],
  energySimulation: null,
  busy: null,
  error: null,
  info: null,
};

function toFlowError(e: unknown): FlowError {
  if (e instanceof ApiError) return { message: e.message, connectivity: e.isConnectivity, code: e.code };
  return { message: '发生未知错误', connectivity: false, code: null };
}

const NO_CONTEXT: Outcome<never> = { ok: false, error: { message: '还没有选择人物', connectivity: false, code: null } };

export function useRestFlow(api: LivingMindApi) {
  const [state, setState] = useState<RestFlowState>(initial);
  const stateRef = useRef(state);
  stateRef.current = state;

  const patch = useCallback((p: Partial<RestFlowState>) => setState((s) => ({ ...s, ...p })), []);

  const context = useCallback((): RequestContext | null => {
    const s = stateRef.current;
    if (!s.data || !s.personId) return null;
    return { accountId: DEMO_ACCOUNT_ID, personId: s.personId, spaceId: s.data.defaultSpaceId };
  }, []);

  const applyBootstrap = useCallback(
    (data: BootstrapResponse, keepPerson: boolean) =>
      setState((s) => ({
        ...s,
        phase: 'ready',
        data,
        mode: s.data ? s.mode : data.planner.defaultMode,
        personId:
          keepPerson && s.personId ? s.personId : (data.activeService?.personId ?? data.persons[0]?.personId ?? null),
        plan: null,
        results: [],
        service: data.activeService ?? null,
        deviceState: data.deviceState,
        deviceStale: false,
        error: null,
      })),
    [],
  );

  const loadActivity = useCallback(
    async (sid: string) => {
      try {
        const res = await api.getActivity(sid);
        patch({ activity: res.items });
      } catch {
        // Activity is secondary; the main error banner is driven by the primary action.
      }
    },
    [api, patch],
  );

  const load = useCallback(async () => {
    patch({ phase: 'loading', error: null });
    try {
      const data = await api.bootstrap();
      applyBootstrap(data, false);
      const [scenes, energySimulation] = await Promise.all([
        api.getScenes().catch(() => ({ items: [] as Scene[] })),
        api.getOfflineEnergySimulation(data.defaultSpaceId).catch(() => null),
      ]);
      patch({ scenes: scenes.items, energySimulation });
      await loadActivity(data.defaultSpaceId);
    } catch (e) {
      patch({ phase: 'error', error: toFlowError(e) });
    }
  }, [api, applyBootstrap, loadActivity, patch]);

  useEffect(() => {
    void load();
  }, [load]);

  // Load the acting person's own memory whenever the person changes.
  const personKey = state.data ? state.personId : null;
  useEffect(() => {
    const ctx = context();
    if (!ctx) return;
    let alive = true;
    patch({ memory: null });
    api
      .getMemory(ctx)
      .then((memory) => alive && patch({ memory }))
      .catch(() => undefined);
    return () => {
      alive = false;
    };
  }, [api, context, patch, personKey]);

  const fail = useCallback(<T,>(e: unknown): Outcome<T> => {
    const err = toFlowError(e);
    // Connectivity problems mean the shown device state may no longer be true.
    setState((s) => ({ ...s, busy: null, error: err, deviceStale: s.deviceStale || err.connectivity }));
    return { ok: false, error: err };
  }, []);

  const selectPerson = useCallback(
    (personId: string) => {
      const s = stateRef.current;
      if (s.personId === personId) return;
      // A proposed plan belongs to one person; switching clears it.
      patch({ personId, plan: null, results: [], info: null, error: null });
    },
    [patch],
  );

  /** Demo PIN check, then switch. Not authentication. Errors stay local to the PIN dialog. */
  const unlockPerson = useCallback(
    async (personId: string, pin: string | null): Promise<Outcome<true>> => {
      patch({ busy: 'unlock' });
      try {
        await api.unlockPerson(personId, pin);
        patch({ busy: null });
        selectPerson(personId);
        return { ok: true, value: true };
      } catch (e) {
        patch({ busy: null });
        return { ok: false, error: toFlowError(e) };
      }
    },
    [api, patch, selectPerson],
  );

  /** Main Agent entry: plan or answer. */
  const sendMessage = useCallback(
    async (text: string, wakeTime: '06:30' | '07:00' | '07:30' = '07:00'): Promise<Outcome<AssistantReply>> => {
      const ctx = context();
      if (!ctx || !text.trim()) return NO_CONTEXT;
      patch({ busy: 'plan', error: null, info: null });
      try {
        const reply = await api.sendMessage({ context: ctx, text: text.trim(), mode: stateRef.current.mode, wakeTime });
        patch(reply.plan ? { plan: reply.plan, results: [], busy: null } : { busy: null });
        await loadActivity(ctx.spaceId);
        return { ok: true, value: reply };
      } catch (e) {
        return fail(e);
      }
    },
    [api, context, fail, loadActivity, patch],
  );

  const updatePreference = useCallback(
    async (preference: RestPreference): Promise<Outcome<MemoryView>> => {
      const ctx = context();
      if (!ctx) return NO_CONTEXT;
      patch({ busy: 'memory' });
      try {
        const memory = await api.updatePreference(ctx, preference);
        patch({ memory, busy: null, info: '偏好已保存，下一次计划会使用新偏好' });
        await loadActivity(ctx.spaceId);
        return { ok: true, value: memory };
      } catch (e) {
        patch({ busy: null });
        return { ok: false, error: toFlowError(e) };
      }
    },
    [api, context, loadActivity, patch],
  );

  const setEnergyMode = useCallback(
    async (mode: EnergyMode): Promise<Outcome<true>> => {
      const ctx = context();
      if (!ctx) return NO_CONTEXT;
      patch({ busy: 'energy', error: null });
      try {
        const space = await api.setEnergyMode(ctx, mode);
        setState((s) =>
          s.data
            ? {
                ...s,
                busy: null,
                data: { ...s.data, spaces: s.data.spaces.map((x) => (x.spaceId === space.spaceId ? space : x)) },
              }
            : { ...s, busy: null },
        );
        await loadActivity(ctx.spaceId);
        return { ok: true, value: true };
      } catch (e) {
        return fail(e);
      }
    },
    [api, context, fail, loadActivity, patch],
  );

  const createPlan = useCallback(
    async (utterance: string, wakeTime: '06:30' | '07:00' | '07:30' = '07:00'): Promise<Outcome<Plan>> => {
      const ctx = context();
      if (!ctx || !utterance.trim()) return NO_CONTEXT;
      patch({ busy: 'plan', error: null, info: null });
      try {
        const plan = await api.createRestPlan({ context: ctx, utterance: utterance.trim(), mode: stateRef.current.mode, wakeTime });
        patch({ plan, results: [], busy: null });
        await loadActivity(ctx.spaceId);
        return { ok: true, value: plan };
      } catch (e) {
        return fail(e);
      }
    },
    [api, context, fail, loadActivity, patch],
  );

  const confirm = useCallback(async (): Promise<Outcome<ConfirmPlanResponse>> => {
    const ctx = context();
    const plan = stateRef.current.plan;
    if (!ctx || !plan) return NO_CONTEXT;
    patch({ busy: 'confirm', error: null, info: null });
    try {
      const res = await api.confirmPlan(plan.planId, { context: ctx, planVersion: plan.version });
      patch({
        plan: res.plan,
        service: res.service ?? stateRef.current.service,
        results: res.results,
        deviceState: res.deviceState,
        deviceStale: false,
        busy: null,
        info: res.repeated ? '该计划已经执行过，本次没有重复执行' : null,
      });
      await loadActivity(ctx.spaceId);
      return { ok: true, value: res };
    } catch (e) {
      if (e instanceof ApiError && (e.code === 'PLAN_EXPIRED' || e.code === 'PLAN_INVALIDATED')) {
        const status = e.code === 'PLAN_EXPIRED' ? 'expired' : 'invalidated';
        setState((s) => ({ ...s, plan: s.plan ? { ...s.plan, status } : null }));
      }
      const out = fail<ConfirmPlanResponse>(e);
      await loadActivity(ctx.spaceId);
      return out;
    }
  }, [api, context, fail, loadActivity, patch]);

  const stop = useCallback(async (): Promise<Outcome<StopServiceResponse>> => {
    const ctx = context();
    const service = stateRef.current.service;
    if (!ctx || !service) return NO_CONTEXT;
    patch({ busy: 'stop', error: null, info: null });
    try {
      const res = await api.stopService(service.serviceId, { context: ctx });
      patch({ service: res.service, deviceState: res.deviceState, deviceStale: false, busy: null });
      await loadActivity(ctx.spaceId);
      return { ok: true, value: res };
    } catch (e) {
      return fail(e);
    }
  }, [api, context, fail, loadActivity, patch]);

  const injectEvent = useCallback(
    async (roomTempC: number): Promise<Outcome<EventResult>> => {
      const ctx = context();
      if (!ctx) return NO_CONTEXT;
      patch({ busy: 'event', error: null, info: null });
      try {
        const res = await api.injectEvent(ctx.spaceId, { context: ctx, type: 'room_temperature_changed', roomTempC });
        patch({
          service: res.service ?? stateRef.current.service,
          deviceState: res.deviceState,
          deviceStale: false,
          busy: null,
        });
        await loadActivity(ctx.spaceId);
        return { ok: true, value: res };
      } catch (e) {
        return fail(e);
      }
    },
    [api, context, fail, loadActivity, patch],
  );

  /** Simulated night clock. minutes=null jumps to the next pending step. */
  const advanceClock = useCallback(
    async (minutes: number | null = null): Promise<Outcome<AdvanceClockResponse>> => {
      const ctx = context();
      const service = stateRef.current.service;
      if (!ctx || !service) return NO_CONTEXT;
      patch({ busy: 'clock', error: null });
      try {
        const res = await api.advanceClock(service.serviceId, { context: ctx, minutes });
        patch({ service: res.service, deviceState: res.deviceState, deviceStale: false, busy: null });
        await loadActivity(ctx.spaceId);
        return { ok: true, value: res };
      } catch (e) {
        return fail(e);
      }
    },
    [api, context, fail, loadActivity, patch],
  );

  /** Explicit pitch-demo sleep signal. It advances only the first "sleep" schedule step. */
  const simulateSleep = useCallback(async (): Promise<Outcome<AdvanceClockResponse>> => {
    const ctx = context();
    const service = stateRef.current.service;
    if (!ctx || !service) return NO_CONTEXT;
    patch({ busy: 'clock', error: null });
    try {
      const res = await api.simulateSleep(service.serviceId, { context: ctx });
      patch({ service: res.service, deviceState: res.deviceState, deviceStale: false, busy: null, info: res.note });
      await loadActivity(ctx.spaceId);
      return { ok: true, value: res };
    } catch (e) {
      return fail(e);
    }
  }, [api, context, fail, loadActivity, patch]);

  const refresh = useCallback(async () => {
    const sid = stateRef.current.data?.defaultSpaceId;
    if (!sid) return;
    patch({ busy: 'refresh', error: null });
    try {
      const deviceState = await api.getDeviceState(sid);
      patch({ deviceState, deviceStale: false, busy: null });
      await loadActivity(sid);
    } catch (e) {
      fail(e);
    }
  }, [api, fail, loadActivity, patch]);

  /** Reset demo data. With keepPerson=false the first member (林悦) becomes active again. */
  const resetDemo = useCallback(async (keepPerson = true, info = '演示数据已重置'): Promise<Outcome<true>> => {
    patch({ busy: 'reset', error: null, info: null });
    try {
      const data = await api.resetDemo();
      applyBootstrap(data, keepPerson);
      patch({ busy: null, info, mode: data.planner.defaultMode });
      const ctx = context();
      if (ctx) api.getMemory(ctx).then((memory) => patch({ memory })).catch(() => undefined);
      await loadActivity(data.defaultSpaceId);
      return { ok: true, value: true };
    } catch (e) {
      return fail(e);
    }
  }, [api, applyBootstrap, context, fail, loadActivity, patch]);

  // Re-evaluate time-based rules (plan expiry) while a proposed plan is on screen.
  const [now, setNow] = useState(() => new Date());
  const waiting = state.plan?.status === 'proposed';
  useEffect(() => {
    if (!waiting) return;
    setNow(new Date());
    const timer = setInterval(() => setNow(new Date()), 15000);
    return () => clearInterval(timer);
  }, [waiting]);

  const activeService = state.service?.status === 'active' ? state.service : null;
  const blockReason = useMemo(
    () => planBlockReason(state.plan, activeService, state.personId, now),
    [state.plan, activeService, state.personId, now],
  );
  const person = state.data?.persons.find((p) => p.personId === state.personId) ?? null;
  const space = state.data?.spaces.find((x) => x.spaceId === state.data?.defaultSpaceId) ?? null;

  const actions = useMemo(
    () => ({
      load,
      selectPerson,
      unlockPerson,
      sendMessage,
      updatePreference,
      setEnergyMode,
      setMode: (mode: PlannerMode) => patch({ mode }),
      createPlan,
      confirm,
      stop,
      refresh,
      injectEvent,
      advanceClock,
      simulateSleep,
      resetDemo,
      dismissError: () => patch({ error: null }),
      dismissInfo: () => patch({ info: null }),
    }),
    [load, selectPerson, unlockPerson, sendMessage, updatePreference, setEnergyMode, patch, createPlan, confirm, stop, refresh, injectEvent, advanceClock, simulateSleep, resetDemo],
  );

  return { state, person, space, activeService, blockReason, actions };
}

export type RestFlow = ReturnType<typeof useRestFlow>;

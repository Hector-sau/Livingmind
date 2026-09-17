import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { ApiError, DEMO_ACCOUNT_ID, type LivingMindApi } from '../../services';
import type {
  ActionResult,
  ActivityRecord,
  BootstrapResponse,
  DeviceState,
  Plan,
  PlannerMode,
  RequestContext,
  Service,
} from '../../services/types';
import { planBlockReason } from './planGate';

export type Busy = null | 'plan' | 'confirm' | 'stop' | 'refresh' | 'reset' | 'event';

export interface FlowError {
  message: string;
  connectivity: boolean;
}

export interface RestFlowState {
  phase: 'loading' | 'error' | 'ready';
  data: BootstrapResponse | null;
  personId: string | null;
  utterance: string;
  mode: PlannerMode;
  plan: Plan | null;
  service: Service | null;
  results: ActionResult[];
  deviceState: DeviceState | null;
  deviceStale: boolean;
  activity: ActivityRecord[];
  busy: Busy;
  error: FlowError | null;
  info: string | null;
}

const initial: RestFlowState = {
  phase: 'loading',
  data: null,
  personId: null,
  utterance: '我想休息',
  mode: 'rule',
  plan: null,
  service: null,
  results: [],
  deviceState: null,
  deviceStale: false,
  activity: [],
  busy: null,
  error: null,
  info: null,
};

function toFlowError(e: unknown): FlowError {
  if (e instanceof ApiError) return { message: e.message, connectivity: e.isConnectivity };
  return { message: '发生未知错误', connectivity: false };
}

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
      await loadActivity(data.defaultSpaceId);
    } catch (e) {
      patch({ phase: 'error', error: toFlowError(e) });
    }
  }, [api, applyBootstrap, loadActivity, patch]);

  useEffect(() => {
    void load();
  }, [load]);

  const fail = useCallback((e: unknown) => {
    const err = toFlowError(e);
    // Connectivity problems mean the shown device state may no longer be true.
    setState((s) => ({ ...s, busy: null, error: err, deviceStale: s.deviceStale || err.connectivity }));
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

  const createPlan = useCallback(async () => {
    const ctx = context();
    const s = stateRef.current;
    if (!ctx || !s.utterance.trim()) return;
    patch({ busy: 'plan', error: null, info: null });
    try {
      const plan = await api.createRestPlan({ context: ctx, utterance: s.utterance.trim(), mode: s.mode });
      patch({ plan, results: [], busy: null });
      await loadActivity(ctx.spaceId);
    } catch (e) {
      fail(e);
    }
  }, [api, context, fail, loadActivity, patch]);

  const confirm = useCallback(async () => {
    const ctx = context();
    const plan = stateRef.current.plan;
    if (!ctx || !plan) return;
    patch({ busy: 'confirm', error: null, info: null });
    try {
      const res = await api.confirmPlan(plan.planId, { context: ctx, planVersion: plan.version });
      patch({
        plan: res.plan,
        service: res.service,
        results: res.results,
        deviceState: res.deviceState,
        deviceStale: false,
        busy: null,
        info: res.repeated ? '该计划已经执行过，本次没有重复执行' : null,
      });
      await loadActivity(ctx.spaceId);
    } catch (e) {
      if (e instanceof ApiError && (e.code === 'PLAN_EXPIRED' || e.code === 'PLAN_INVALIDATED')) {
        const status = e.code === 'PLAN_EXPIRED' ? 'expired' : 'invalidated';
        setState((s) => ({ ...s, plan: s.plan ? { ...s.plan, status } : null }));
      }
      fail(e);
      await loadActivity(ctx.spaceId);
    }
  }, [api, context, fail, loadActivity, patch]);

  const stop = useCallback(async () => {
    const ctx = context();
    const service = stateRef.current.service;
    if (!ctx || !service) return;
    patch({ busy: 'stop', error: null, info: null });
    try {
      const res = await api.stopService(service.serviceId, { context: ctx });
      patch({
        service: res.service,
        deviceState: res.deviceState,
        deviceStale: false,
        busy: null,
        info: '服务已停止，设备保持当前状态',
      });
      await loadActivity(ctx.spaceId);
    } catch (e) {
      fail(e);
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

  const injectEvent = useCallback(
    async (roomTempC: number) => {
      const ctx = context();
      if (!ctx) return;
      patch({ busy: 'event', error: null, info: null });
      try {
        const res = await api.injectEvent(ctx.spaceId, { context: ctx, type: 'room_temperature_changed', roomTempC });
        patch({
          service: res.service ?? stateRef.current.service,
          deviceState: res.deviceState,
          deviceStale: false,
          busy: null,
          info:
            res.outcome === 'adjusted'
              ? `模拟事件：室温 ${roomTempC}°C → 已自动调整：${res.plan?.summary ?? ''}`
              : `模拟事件：室温 ${roomTempC}°C → 未调整：${res.reason ?? ''}`,
        });
        await loadActivity(ctx.spaceId);
      } catch (e) {
        fail(e);
      }
    },
    [api, context, fail, loadActivity, patch],
  );

  const resetDemo = useCallback(async () => {
    patch({ busy: 'reset', error: null, info: null });
    try {
      const data = await api.resetDemo();
      applyBootstrap(data, true);
      patch({ busy: null, info: '演示数据已重置' });
      await loadActivity(data.defaultSpaceId);
    } catch (e) {
      fail(e);
    }
  }, [api, applyBootstrap, fail, loadActivity, patch]);

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

  const actions = useMemo(
    () => ({
      load,
      selectPerson,
      setUtterance: (utterance: string) => patch({ utterance }),
      setMode: (mode: PlannerMode) => patch({ mode }),
      createPlan,
      confirm,
      stop,
      refresh,
      injectEvent,
      resetDemo,
      dismissError: () => patch({ error: null }),
      dismissInfo: () => patch({ info: null }),
    }),
    [load, selectPerson, patch, createPlan, confirm, stop, refresh, injectEvent, resetDemo],
  );

  return { state, activeService, blockReason, actions };
}

export type RestFlow = ReturnType<typeof useRestFlow>;

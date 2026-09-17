// Real backend client. Failures are surfaced as ApiError; there is NO fallback to mock data.
import { ApiError, DEMO_ACCOUNT_ID, type LivingMindApi } from '../api';
import type {
  ActivityResponse,
  BootstrapResponse,
  ConfirmPlanResponse,
  DeviceState,
  ErrorResponse,
  EventResult,
  Plan,
  StopServiceResponse,
} from '../types';

export interface HttpOptions {
  baseUrl: string;
  /** Default timeout for every request. */
  timeoutMs: number;
  fetchImpl?: typeof fetch;
  accountId?: string;
}

export function createHttpApi(options: HttpOptions): LivingMindApi {
  const fetchImpl = options.fetchImpl ?? fetch;
  const accountId = options.accountId ?? DEMO_ACCOUNT_ID;
  const q = `accountId=${encodeURIComponent(accountId)}`;
  // Planning may wait for a model. Once the backend tells us its model timeout, give plan
  // requests that long plus a margin, so the app never gives up before the backend falls back.
  const PLAN_MARGIN_MS = 3000;
  let planTimeoutMs = options.timeoutMs;
  const learnPlannerTimeout = (res: BootstrapResponse): BootstrapResponse => {
    planTimeoutMs = Math.max(options.timeoutMs, res.planner.timeoutMs + PLAN_MARGIN_MS);
    return res;
  };

  async function request<T>(method: 'GET' | 'POST', path: string, body?: unknown, timeoutMs = options.timeoutMs): Promise<T> {
    const controller = new AbortController();
    let timedOut = false;
    const timer = setTimeout(() => {
      timedOut = true;
      controller.abort();
    }, timeoutMs);
    let res: Response;
    try {
      res = await fetchImpl(`${options.baseUrl}${path}`, {
        method,
        headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
        body: body === undefined ? undefined : JSON.stringify(body),
        signal: controller.signal,
      });
    } catch {
      throw timedOut
        ? new ApiError('TIMEOUT', '后端响应超时，显示的状态可能已过期')
        : new ApiError('NETWORK_ERROR', '无法连接后端，显示的状态可能已过期');
    } finally {
      clearTimeout(timer);
    }

    let payload: unknown = null;
    try {
      payload = await res.json();
    } catch {
      payload = null;
    }
    if (!res.ok) {
      const err = (payload as ErrorResponse | null)?.error;
      if (err && typeof err.code === 'string') {
        throw new ApiError(err.code, err.message, res.status, (err.details as Record<string, unknown> | null) ?? null);
      }
      throw new ApiError('BAD_RESPONSE', `后端返回异常（HTTP ${res.status}）`, res.status);
    }
    if (payload === null) throw new ApiError('BAD_RESPONSE', '后端返回内容无法解析', res.status);
    return payload as T;
  }

  return {
    mode: 'http',
    bootstrap: () => request<BootstrapResponse>('GET', `/api/bootstrap?${q}`).then(learnPlannerTimeout),
    getDeviceState: (spaceId) =>
      request<DeviceState>('GET', `/api/spaces/${encodeURIComponent(spaceId)}/devices?${q}`),
    createRestPlan: (req) => request<Plan>('POST', '/api/plans/rest', req, planTimeoutMs),
    confirmPlan: (planId, req) =>
      request<ConfirmPlanResponse>('POST', `/api/plans/${encodeURIComponent(planId)}/confirm`, req),
    stopService: (serviceId, req) =>
      request<StopServiceResponse>('POST', `/api/services/${encodeURIComponent(serviceId)}/stop`, req),
    // An event may trigger model re-planning, so it gets the plan timeout too.
    injectEvent: (spaceId, req) =>
      request<EventResult>('POST', `/api/spaces/${encodeURIComponent(spaceId)}/events`, req, planTimeoutMs),
    getActivity: (spaceId, limit = 50) =>
      request<ActivityResponse>('GET', `/api/spaces/${encodeURIComponent(spaceId)}/activity?${q}&limit=${limit}`),
    resetDemo: () => request<BootstrapResponse>('POST', `/api/demo/reset?${q}`).then(learnPlannerTimeout),
  };
}

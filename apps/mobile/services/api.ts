import type {
  ActivityResponse,
  BootstrapResponse,
  ConfirmPlanRequest,
  ConfirmPlanResponse,
  CreateRestPlanRequest,
  DeviceState,
  ErrorCode,
  Plan,
  StopServiceRequest,
  StopServiceResponse,
} from './types';

/** The only way pages talk to "the system". Pages never touch devices directly. */
export interface LivingMindApi {
  readonly mode: 'mock' | 'http';
  bootstrap(): Promise<BootstrapResponse>;
  getDeviceState(spaceId: string): Promise<DeviceState>;
  createRestPlan(req: CreateRestPlanRequest): Promise<Plan>;
  confirmPlan(planId: string, req: ConfirmPlanRequest): Promise<ConfirmPlanResponse>;
  stopService(serviceId: string, req: StopServiceRequest): Promise<StopServiceResponse>;
  getActivity(spaceId: string, limit?: number): Promise<ActivityResponse>;
  resetDemo(): Promise<BootstrapResponse>;
}

/** Client-side failure kinds in addition to backend error codes. */
export type ClientErrorCode = 'NETWORK_ERROR' | 'TIMEOUT' | 'BAD_RESPONSE';

export class ApiError extends Error {
  readonly code: ErrorCode | ClientErrorCode;
  readonly status: number | null;
  readonly details: Record<string, unknown> | null;

  constructor(
    code: ErrorCode | ClientErrorCode,
    message: string,
    status: number | null = null,
    details: Record<string, unknown> | null = null,
  ) {
    super(message);
    this.name = 'ApiError';
    this.code = code;
    this.status = status;
    this.details = details;
  }

  /** True when we could not reach the backend at all, so any shown state may be stale. */
  get isConnectivity(): boolean {
    return this.code === 'NETWORK_ERROR' || this.code === 'TIMEOUT';
  }
}

/** Demo identity. This is not authentication (see docs/architecture.md). */
export const DEMO_ACCOUNT_ID = 'demo-account';

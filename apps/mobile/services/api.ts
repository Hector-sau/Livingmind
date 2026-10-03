import type {
  ActionExecution,
  ActivityResponse,
  AdvanceClockRequest,
  AdvanceClockResponse,
  SimulateSleepRequest,
  AssistantMessageRequest,
  AssistantReply,
  EnergyMode,
  MemoryView,
  RestPreference,
  Space,
  BootstrapResponse,
  ConfirmPlanRequest,
  ConfirmPlanResponse,
  CreateRestPlanRequest,
  DeviceControlRequest,
  DeviceControlResponse,
  DeviceState,
  ErrorCode,
  EventResult,
  OfflineEnergySimulation,
  InjectEventRequest,
  RequestContext,
  Plan,
  ScenesResponse,
  StopServiceRequest,
  UndoRequest,
  UndoResponse,
  UnlockPersonResponse,
  StopServiceResponse,
} from './types';

/** The only way pages talk to "the system". Pages never touch devices directly. */
export interface LivingMindApi {
  readonly mode: 'mock' | 'http';
  bootstrap(): Promise<BootstrapResponse>;
  /** Demo PIN check before switching person. NOT authentication. */
  unlockPerson(personId: string, pin: string | null): Promise<UnlockPersonResponse>;
  getScenes(): Promise<ScenesResponse>;
  getDeviceState(spaceId: string): Promise<DeviceState>;
  /** Main Agent entry for the chat: returns a plan to confirm or a short answer. */
  sendMessage(req: AssistantMessageRequest): Promise<AssistantReply>;
  createRestPlan(req: CreateRestPlanRequest): Promise<Plan>;
  /** Only the acting person's own preference plus shared space rules. */
  getMemory(ctx: RequestContext): Promise<MemoryView>;
  updatePreference(ctx: RequestContext, preference: RestPreference): Promise<MemoryView>;
  setEnergyMode(ctx: RequestContext, mode: EnergyMode): Promise<Space>;
  /** Supplied fixed-day MATD3 evidence. Read-only; never an App control loop. */
  getOfflineEnergySimulation(spaceId: string): Promise<OfflineEnergySimulation>;
  confirmPlan(planId: string, req: ConfirmPlanRequest): Promise<ConfirmPlanResponse>;
  /** Query a saved receipt only. Never confirms a plan or resends a device command. */
  reconcileAction(actionId: string, ctx: RequestContext): Promise<ActionExecution>;
  getActions(ctx: RequestContext): Promise<ActionExecution[]>;
  stopService(serviceId: string, req: StopServiceRequest): Promise<StopServiceResponse>;
  /** Simulated night clock (demo only). minutes=null jumps to the next pending step. */
  advanceClock(serviceId: string, req: AdvanceClockRequest): Promise<AdvanceClockResponse>;
  /** Explicit pitch-demo sleep signal; not a real sensor event. */
  simulateSleep(serviceId: string, req: SimulateSleepRequest): Promise<AdvanceClockResponse>;
  /** Simulated environment event (demo only). May lead to one automatic adjustment. */
  injectEvent(spaceId: string, req: InjectEventRequest): Promise<EventResult>;
  /**
   * Direct control from the device panel. Executes straight away — the safety net is the
   * returned undo window, not a confirmation dialog. Still goes through the backend
   * executor: whitelist, range, epoch guard, write, read back.
   */
  controlDevice(spaceId: string, req: DeviceControlRequest): Promise<DeviceControlResponse>;
  /** Put the device back on the exact value it held before, while the window is open. */
  undoDeviceControl(undoId: string, req: UndoRequest): Promise<UndoResponse>;
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

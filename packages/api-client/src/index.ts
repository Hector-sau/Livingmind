// Friendly aliases over the generated schema. Only types live here (erased at build time),
// so the app can import them with `import type` without bundler configuration.
import type { components, operations } from './schema';

type Schemas = components['schemas'];

export type RestPreference = Schemas['RestPreference'];
export type Person = Schemas['Person'];
export type Space = Schemas['Space'];
export type Scene = Schemas['Scene'];
export type ScenesResponse = Schemas['ScenesResponse'];
export type UnlockPersonRequest = Schemas['UnlockPersonRequest'];
export type UnlockPersonResponse = Schemas['UnlockPersonResponse'];
export type DemoAccount = Schemas['DemoAccount'];
export type RequestContext = Schemas['RequestContext'];
export type DeviceAction = Schemas['DeviceAction'];
export type DeviceState = Schemas['DeviceState'];
export type Plan = Schemas['Plan'];
export type PlanGeneration = Schemas['PlanGeneration'];
export type PlannerInfo = Schemas['PlannerInfo'];
export type AgentStep = Schemas['AgentStep'];
export type EnergyAdvice = Schemas['EnergyAdvice'];
export type OfflineEnergyMetric = Schemas['OfflineEnergyMetric'];
export type OfflineEnergyAsset = Schemas['OfflineEnergyAsset'];
export type OfflineEnergyProfilePoint = Schemas['OfflineEnergyProfilePoint'];
export type OfflineEnergySimulation = Schemas['OfflineEnergySimulation'];
export type AssistantMessageRequest = Schemas['AssistantMessageRequest'];
export type AssistantReply = Schemas['AssistantReply'];
export type MemoryView = Schemas['MemoryView'];
export type SpaceRule = Schemas['SpaceRule'];
export type UpdatePreferenceRequest = Schemas['UpdatePreferenceRequest'];
export type SetEnergyModeRequest = Schemas['SetEnergyModeRequest'];
export type Service = Schemas['Service'];
export type ScheduledStep = Schemas['ScheduledStep'];
export type AdvanceClockRequest = Schemas['AdvanceClockRequest'];
export type AdvanceClockResponse = Schemas['AdvanceClockResponse'];
export type ActionResult = Schemas['ActionResult'];
export type ActivityRecord = Schemas['ActivityRecord'];
export type CreateRestPlanRequest = Schemas['CreateRestPlanRequest'];
export type ConfirmPlanRequest = Schemas['ConfirmPlanRequest'];
export type StopServiceRequest = Schemas['StopServiceRequest'];
export type InjectEventRequest = Schemas['InjectEventRequest'];
export type EventResult = Schemas['EventResult'];
export type BootstrapResponse = Schemas['BootstrapResponse'];
export type ConfirmPlanResponse = Schemas['ConfirmPlanResponse'];
export type StopServiceResponse = Schemas['StopServiceResponse'];
export type ActivityResponse = Schemas['ActivityResponse'];
export type ErrorBody = Schemas['ErrorBody'];
export type ErrorResponse = Schemas['ErrorResponse'];

export type ErrorCode = ErrorBody['code'];
export type PlanStatus = Plan['status'];
export type PlanSource = Plan['source'];
export type PlannerMode = PlanGeneration['modeRequested'];
export type EnergyMode = Space['energyMode'];
export type AgentName = AgentStep['agent'];
export type ServiceStatus = Service['status'];
export type SchedulePhase = ScheduledStep['phase'];
export type ScheduleStepStatus = ScheduledStep['status'];
export type DataSource = DeviceState['source'];
export type ActivityKind = ActivityRecord['kind'];
export type ActivitySource = ActivityRecord['source'];
export type ActionOutcome = ActionResult['outcome'];

export type { components, operations };

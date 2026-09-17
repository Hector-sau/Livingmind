// Friendly aliases over the generated schema. Only types live here (erased at build time),
// so the app can import them with `import type` without bundler configuration.
import type { components, operations } from './schema';

type Schemas = components['schemas'];

export type RestPreference = Schemas['RestPreference'];
export type Person = Schemas['Person'];
export type Space = Schemas['Space'];
export type DemoAccount = Schemas['DemoAccount'];
export type RequestContext = Schemas['RequestContext'];
export type DeviceAction = Schemas['DeviceAction'];
export type DeviceState = Schemas['DeviceState'];
export type Plan = Schemas['Plan'];
export type Service = Schemas['Service'];
export type ActionResult = Schemas['ActionResult'];
export type ActivityRecord = Schemas['ActivityRecord'];
export type CreateRestPlanRequest = Schemas['CreateRestPlanRequest'];
export type ConfirmPlanRequest = Schemas['ConfirmPlanRequest'];
export type StopServiceRequest = Schemas['StopServiceRequest'];
export type BootstrapResponse = Schemas['BootstrapResponse'];
export type ConfirmPlanResponse = Schemas['ConfirmPlanResponse'];
export type StopServiceResponse = Schemas['StopServiceResponse'];
export type ActivityResponse = Schemas['ActivityResponse'];
export type ErrorBody = Schemas['ErrorBody'];
export type ErrorResponse = Schemas['ErrorResponse'];

export type ErrorCode = ErrorBody['code'];
export type PlanStatus = Plan['status'];
export type PlanSource = Plan['source'];
export type ServiceStatus = Service['status'];
export type DataSource = DeviceState['source'];
export type ActivityKind = ActivityRecord['kind'];
export type ActivitySource = ActivityRecord['source'];
export type ActionOutcome = ActionResult['outcome'];

export type { components, operations };

import { appConfig, type AppConfig } from '../config';
import type { LivingMindApi } from './api';
import { createHttpApi } from './http/httpApi';
import { createMockApi } from './mock/mockApi';

export function createApi(config: AppConfig): LivingMindApi {
  if (config.mode === 'http' && config.apiBaseUrl) {
    return createHttpApi({ baseUrl: config.apiBaseUrl, timeoutMs: config.requestTimeoutMs });
  }
  return createMockApi();
}

export const api: LivingMindApi = createApi(appConfig);

export { ApiError, DEMO_ACCOUNT_ID } from './api';
export type { LivingMindApi } from './api';

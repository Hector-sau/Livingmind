// App runtime config. Only EXPO_PUBLIC_* values are available in the app bundle,
// so never put secrets here.

export type ApiMode = 'mock' | 'http';

export interface AppConfig {
  mode: ApiMode;
  apiBaseUrl: string | null;
  requestTimeoutMs: number;
}

export function resolveConfig(env: Record<string, string | undefined>): AppConfig {
  const raw = (env.EXPO_PUBLIC_API_BASE_URL ?? '').trim();
  const apiBaseUrl = raw ? raw.replace(/\/+$/, '') : null;
  return {
    // No silent fallback: http mode only when a base URL is configured explicitly.
    mode: apiBaseUrl ? 'http' : 'mock',
    apiBaseUrl,
    requestTimeoutMs: 8000,
  };
}

export const appConfig: AppConfig = resolveConfig({
  EXPO_PUBLIC_API_BASE_URL: process.env.EXPO_PUBLIC_API_BASE_URL,
});

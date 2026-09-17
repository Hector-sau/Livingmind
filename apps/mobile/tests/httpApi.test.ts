import assert from 'node:assert/strict';
import { test } from 'node:test';

import { ApiError } from '../services/api';
import { createHttpApi } from '../services/http/httpApi';

test('unreachable backend surfaces NETWORK_ERROR instead of fake success', async () => {
  const api = createHttpApi({
    baseUrl: 'http://backend.invalid',
    timeoutMs: 1000,
    fetchImpl: async () => {
      throw new TypeError('Network request failed');
    },
  });
  await assert.rejects(api.bootstrap(), (e: unknown) => e instanceof ApiError && e.code === 'NETWORK_ERROR' && e.isConnectivity);
});

test('slow backend surfaces TIMEOUT', async () => {
  const api = createHttpApi({
    baseUrl: 'http://backend.invalid',
    timeoutMs: 20,
    fetchImpl: (_url, init) =>
      new Promise((_resolve, reject) => {
        init?.signal?.addEventListener('abort', () => reject(new Error('aborted')));
      }),
  });
  await assert.rejects(api.bootstrap(), (e: unknown) => e instanceof ApiError && e.code === 'TIMEOUT');
});

test('backend error body is mapped to ApiError code', async () => {
  const api = createHttpApi({
    baseUrl: 'http://backend.invalid',
    timeoutMs: 1000,
    fetchImpl: async () =>
      new Response(JSON.stringify({ error: { code: 'PLAN_EXPIRED', message: '计划已过期', details: null } }), {
        status: 409,
        headers: { 'Content-Type': 'application/json' },
      }),
  });
  await assert.rejects(
    api.confirmPlan('p1', { context: { accountId: 'demo-account', personId: 'x', spaceId: 'y' }, planVersion: 1 }),
    (e: unknown) => e instanceof ApiError && e.code === 'PLAN_EXPIRED' && e.status === 409,
  );
});

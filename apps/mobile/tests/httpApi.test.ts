import assert from 'node:assert/strict';
import { test } from 'node:test';

import { ApiError } from '../services/api';
import { createHttpApi } from '../services/http/httpApi';

test('receipt reconciliation calls only the query endpoint with the acting context', async () => {
  const calls: { url: string; method?: string; body: unknown }[] = [];
  const api = createHttpApi({ baseUrl: 'http://backend.invalid', timeoutMs: 1000,
    fetchImpl: async (url, init) => {
      calls.push({ url: String(url), method: init?.method, body: JSON.parse(String(init?.body)) });
      return new Response(JSON.stringify({ actionId: 'a/1', status: 'unknown' }));
    } });
  const context = { accountId: 'demo-account', personId: 'person-lin', spaceId: 's' };
  assert.equal((await api.reconcileAction('a/1', context)).status, 'unknown');
  assert.deepEqual(calls, [{ url: 'http://backend.invalid/api/actions/a%2F1/reconcile', method: 'POST', body: { context } }]);
});

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

test('plan requests wait for the backend model timeout plus a margin', async () => {
  const planner = { defaultMode: 'model', modelConfigured: true, provider: 'deepseek', model: 'm', timeoutMs: 50 } as const;
  const json = (body: unknown) => new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } });
  const api = createHttpApi({
    baseUrl: 'http://backend.invalid',
    timeoutMs: 20, // shorter than the simulated model wait below
    fetchImpl: (url, init) =>
      new Promise((resolve, reject) => {
        init?.signal?.addEventListener('abort', () => reject(new Error('aborted')));
        const u = String(url);
        if (u.includes('/api/bootstrap')) resolve(json({ planner }));
        else setTimeout(() => resolve(json({ planId: 'p' })), 60); // "model" takes 60 ms
      }),
  });
  await api.bootstrap();
  const plan = await api.createRestPlan({ context: { accountId: 'demo-account', personId: 'a', spaceId: 's' }, utterance: 'x' });
  assert.equal(plan.planId, 'p');
  // other requests keep the short default
  await assert.rejects(api.getDeviceState('s'), (e: unknown) => e instanceof ApiError && e.code === 'TIMEOUT');
});

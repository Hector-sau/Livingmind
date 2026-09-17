import assert from 'node:assert/strict';
import { test } from 'node:test';

import { ApiError } from '../services/api';
import { createMockApi } from '../services/mock/mockApi';

const ctx = (personId: string) => ({ accountId: 'demo-account', personId, spaceId: 'space-home-bedroom' });

test('creating a plan does not change devices; confirming does', async () => {
  const api = createMockApi({ latencyMs: 0 });
  const before = (await api.bootstrap()).deviceState;
  const plan = await api.createRestPlan({ context: ctx('person-lin'), utterance: '我想休息' });
  assert.deepEqual(await api.getDeviceState('space-home-bedroom'), before);
  const res = await api.confirmPlan(plan.planId, { context: ctx('person-lin'), planVersion: 1 });
  assert.equal(res.deviceState.lightBrightness, 15);
  assert.equal(res.deviceState.source, 'frontend_mock');
  assert.equal(res.repeated, false);
});

test('different persons get different plans', async () => {
  const api = createMockApi({ latencyMs: 0 });
  const a = await api.createRestPlan({ context: ctx('person-lin'), utterance: '我想休息' });
  const b = await api.createRestPlan({ context: ctx('person-chen'), utterance: '我想休息' });
  assert.notDeepEqual(a.actions.map((x) => x.value), b.actions.map((x) => x.value));
});

test('repeat confirm does not execute again; stop invalidates older plans', async () => {
  const api = createMockApi({ latencyMs: 0 });
  const plan = await api.createRestPlan({ context: ctx('person-lin'), utterance: '我想休息' });
  const pending = await api.createRestPlan({ context: ctx('person-lin'), utterance: '我想休息' });
  const first = await api.confirmPlan(plan.planId, { context: ctx('person-lin'), planVersion: 1 });
  const again = await api.confirmPlan(plan.planId, { context: ctx('person-lin'), planVersion: 1 });
  assert.equal(again.repeated, true);
  assert.equal(again.deviceState.version, first.deviceState.version);

  await api.stopService(first.service.serviceId, { context: ctx('person-lin') });
  await assert.rejects(
    api.confirmPlan(pending.planId, { context: ctx('person-lin'), planVersion: 1 }),
    (e: unknown) => e instanceof ApiError && e.code === 'PLAN_INVALIDATED',
  );
  const after = await api.getDeviceState('space-home-bedroom');
  assert.equal(after.version, first.deviceState.version);
});

test('unknown person is rejected', async () => {
  const api = createMockApi({ latencyMs: 0 });
  await assert.rejects(
    api.createRestPlan({ context: ctx('someone-else'), utterance: '我想休息' }),
    (e: unknown) => e instanceof ApiError && e.code === 'FORBIDDEN_CONTEXT',
  );
});

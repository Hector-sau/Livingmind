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

  await api.stopService(first.service!.serviceId, { context: ctx('person-lin') });
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

test('mock never pretends to call a model: model mode degrades to a labelled fallback', async () => {
  const api = createMockApi({ latencyMs: 0 });
  const plan = await api.createRestPlan({ context: ctx('person-lin'), utterance: '我想休息', mode: 'model' });
  assert.equal(plan.source, 'frontend_mock');
  assert.equal(plan.generation.modeRequested, 'model');
  assert.ok(plan.generation.fallbackReason);
  const activity = await api.getActivity('space-home-bedroom');
  assert.ok(activity.items.some((i) => i.kind === 'plan_fallback'));
});

test('events: ignored without service, one adjustment, cooldown, ignored after stop', async () => {
  let t = Date.parse('2026-09-17T22:00:00Z');
  const api = createMockApi({ latencyMs: 0, now: () => new Date(t) });
  const c = ctx('person-lin');
  const ev = (roomTempC: number) => api.injectEvent('space-home-bedroom', { context: c, type: 'room_temperature_changed', roomTempC });

  assert.equal((await ev(30)).outcome, 'ignored');

  const plan = await api.createRestPlan({ context: c, utterance: '我想休息' });
  const started = await api.confirmPlan(plan.planId, { context: c, planVersion: 1 });
  const first = await ev(28);
  assert.equal(first.outcome, 'adjusted');
  assert.equal(first.deviceState.acTargetTempC, 24);
  assert.equal(first.service?.adjustments, 1);
  assert.equal(first.plan?.source, 'frontend_mock');

  t += 10_000;
  const cooling = await ev(28);
  assert.equal(cooling.outcome, 'ignored');
  assert.match(cooling.reason ?? '', /冷却/);

  await api.stopService(started.service!.serviceId, { context: c });
  const version = (await api.getDeviceState('space-home-bedroom')).version;
  t += 60_000;
  assert.equal((await ev(30)).outcome, 'ignored');
  assert.equal((await api.getDeviceState('space-home-bedroom')).version, version);
});

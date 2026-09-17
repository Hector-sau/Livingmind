import assert from 'node:assert/strict';
import { test } from 'node:test';

import { advanceMessages, nextPendingStep, scheduleProgress } from '../features/night/schedule';
import { ApiError } from '../services/api';
import { nightClockLabel, nightOffset, nightSchedule } from '../services/mock/agents';
import { createMockApi } from '../services/mock/mockApi';
import type { AdvanceClockResponse } from '../services/types';

const ctx = (personId: string) => ({ accountId: 'demo-account', personId, spaceId: 'space-home-bedroom' });
let n = 0;
const newId = (p: string) => `${p}-${(n += 1)}`;

test('simulated clock labels wrap past midnight', () => {
  assert.equal(nightClockLabel(0), '22:30');
  assert.equal(nightClockLabel(150), '01:00');
  assert.equal(nightOffset('07:00'), 510);
});

test('mock schedule mirrors the backend night rule', () => {
  const lin = { lightBrightness: 15, acTargetTempC: 25, curtainOpenPercent: 0 };
  const steps = nightSchedule(lin, lin, 60, newId);
  assert.deepEqual(steps.map((s) => s.at), ['23:00', '01:00', '06:30', '06:45', '07:00']);
  assert.deepEqual(steps.map((s) => s.phase), ['sleep', 'deep', 'wake', 'wake', 'wake']);
  assert.equal(steps[0].actions[0].label, '灯光关闭');
  assert.equal(steps[1].actions[0].value, 26);
  assert.deepEqual(Object.fromEntries(steps[4].actions.map((a) => [a.device, a.value])), { curtain: 100, light: 60 });
  // deep-night raise never leaves the preference band
  const chen = { lightBrightness: 30, acTargetTempC: 22, curtainOpenPercent: 10 };
  assert.equal(nightSchedule({ ...chen, acTargetTempC: 25 }, chen, 60, newId)[1].actions[0].value, 25);
  assert.match(nightSchedule({ ...chen, acTargetTempC: 25 }, chen, 60, newId)[1].title, /保持/);
});

test('mock night: steps run once, completion ends the service, stop cancels the rest', async () => {
  const api = createMockApi({ latencyMs: 0 });
  const c = ctx('person-lin');
  const plan = await api.createRestPlan({ context: c, utterance: '我想休息' });
  assert.equal(plan.schedule.length, 5);
  const { service } = await api.confirmPlan(plan.planId, { context: c, planVersion: 1 });
  const id = service!.serviceId;
  assert.equal(service!.nightClock, '22:30');

  const first = await api.advanceClock(id, { context: c });
  assert.deepEqual(first.executed.map((s) => s.at), ['23:00']);
  assert.equal(first.deviceState.lightBrightness, 0);
  const idle = await api.advanceClock(id, { context: c, minutes: 30 });
  assert.equal(idle.executed.length, 0);
  assert.equal(idle.note, '下一步在 01:00');

  const rest = await api.advanceClock(id, { context: c, minutes: 720 });
  assert.deepEqual(rest.executed.map((s) => s.at), ['01:00', '06:30', '06:45', '07:00']);
  assert.equal(rest.service.status, 'completed');
  assert.equal(rest.service.nightClock, '07:00');
  assert.deepEqual([rest.deviceState.lightBrightness, rest.deviceState.acTargetTempC, rest.deviceState.curtainOpenPercent], [60, 25, 100]);
  await assert.rejects(api.advanceClock(id, { context: c }), (e: unknown) => e instanceof ApiError && e.code === 'SERVICE_NOT_ACTIVE');

  // a new night, stopped after the first step
  const plan2 = await api.createRestPlan({ context: c, utterance: '我想休息' });
  const s2 = (await api.confirmPlan(plan2.planId, { context: c, planVersion: 1 })).service!;
  await api.advanceClock(s2.serviceId, { context: c });
  const stopped = await api.stopService(s2.serviceId, { context: c });
  assert.deepEqual(stopped.service.schedule.map((s) => s.status), ['done', 'cancelled', 'cancelled', 'cancelled', 'cancelled']);
  const kinds = (await api.getActivity('space-home-bedroom')).items.map((i) => i.kind);
  assert.ok(kinds.includes('schedule_cancelled') && kinds.includes('service_completed'));
});

test('chat lines for a clock advance', async () => {
  const api = createMockApi({ latencyMs: 0 });
  const c = ctx('person-chen');
  const plan = await api.createRestPlan({ context: c, utterance: '我想休息' });
  const service = (await api.confirmPlan(plan.planId, { context: c, planVersion: 1 })).service!;
  assert.equal(nextPendingStep(service)?.at, '23:00');
  const res: AdvanceClockResponse = await api.advanceClock(service.serviceId, { context: c, minutes: 720 });
  assert.deepEqual(scheduleProgress(res.service), { done: 5, total: 5 });
  assert.equal(nextPendingStep(res.service), null);
  const lines = advanceMessages(res);
  assert.equal(lines.length, 6);
  assert.match(lines[0].text, /^模拟时间 23:00 · 入睡：关灯：灯光关闭$/);
  assert.match(lines[5].text, /唤醒完成，整晚服务已结束/);
  const nothing = advanceMessages({ ...res, executed: [], service: { ...res.service, status: 'active' }, note: '下一步在 01:00' });
  assert.deepEqual(nothing, [{ text: '模拟时间 07:00 · 下一步在 01:00', tone: 'info' }]);
});

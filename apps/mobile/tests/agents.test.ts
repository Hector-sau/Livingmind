import assert from 'node:assert/strict';
import { test } from 'node:test';

import { energyAdvise, parseCommand, routeIntent } from '../services/mock/agents';
import { createMockApi } from '../services/mock/mockApi';

// Same cases as backend/tests/test_agents.py::test_router — the mock must route identically.
const ROUTES: [string, string][] = [
  ['我想休息', 'rest'],
  ['把灯关了，我要睡了', 'rest'],
  ['把空调调到24度', 'device_command'],
  ['关灯', 'device_command'],
  ['打开窗帘', 'device_command'],
  ['卧室现在几度', 'status'],
  ['灯现在什么状态', 'status'],
  ['今天股市怎么样', 'other'],
];

test('mock router matches backend routing cases', () => {
  for (const [text, intent] of ROUTES) assert.equal(routeIntent(text), intent, text);
});

test('mock command parser matches backend parser cases', () => {
  const pick = (t: ReturnType<typeof parseCommand>) =>
    Object.fromEntries((['light', 'ac', 'curtain'] as const).filter((k) => t[k] !== null).map((k) => [k, t[k]]));
  assert.deepEqual(pick(parseCommand('把空调调到二十四度', 60)), { ac: 24 });
  assert.deepEqual(pick(parseCommand('灯调到30%', 60)), { light: 30 });
  assert.deepEqual(pick(parseCommand('关灯', 60)), { light: 0 });
  assert.deepEqual(pick(parseCommand('开灯', 60)), { light: 60 });
  assert.deepEqual(pick(parseCommand('窗帘开到50', 60)), { curtain: 50 });
  assert.deepEqual(pick(parseCommand('拉上窗帘', 60)), { curtain: 0 });
});

test('mock energy rules: advise at peak, apply only in eco, stay inside the band', () => {
  const t = { lightBrightness: 15, acTargetTempC: 25, curtainOpenPercent: 0 };
  const comfort = energyAdvise(t, 'comfort_first', 20);
  assert.equal(comfort.recommendedAcC, 25.5);
  assert.equal(comfort.applied, false);
  const eco = energyAdvise(t, 'eco', 20);
  assert.equal(eco.applied, true);
  assert.ok(eco.recommendedAcC <= eco.comfortMaxC);
  assert.equal(energyAdvise(t, 'eco', 9).applied, false);
});

const ctx = (personId: string) => ({ accountId: 'demo-account', personId, spaceId: 'space-home-bedroom' });

test('mock main agent: rest trace, device command without service, answers', async () => {
  const api = createMockApi({ latencyMs: 0, localHour: 20 });
  const rest = await api.sendMessage({ context: ctx('person-lin'), text: '我想休息' });
  assert.equal(rest.kind, 'plan');
  assert.deepEqual(
    (rest.plan!.trace ?? []).map((s) => s.agent),
    ['orchestrator', 'memory', 'experience', 'energy', 'space_execution', 'harness'],
  );
  assert.ok((rest.plan!.trace ?? []).every((s) => s.source === 'frontend_mock'));

  const cmd = await api.sendMessage({ context: ctx('person-lin'), text: '把空调调到24度' });
  assert.equal(cmd.plan!.scenario, 'device_command');
  const done = await api.confirmPlan(cmd.plan!.planId, { context: ctx('person-lin'), planVersion: 1 });
  assert.equal(done.service, null);
  assert.equal(done.deviceState.acTargetTempC, 24);

  const blocked = await api.sendMessage({ context: ctx('person-lin'), text: '空调调到10度' });
  assert.equal(blocked.kind, 'answer');
  const status = await api.sendMessage({ context: ctx('person-lin'), text: '卧室现在几度' });
  assert.equal(status.kind, 'answer');
  assert.match(status.text, /24°C/);
});

test('mock memory: own preference only, edits change the next plan, eco applies', async () => {
  const api = createMockApi({ latencyMs: 0, localHour: 20 });
  const boot = await api.bootstrap();
  assert.ok(boot.persons.every((p) => p.restPreference === null));
  const lin = await api.getMemory(ctx('person-lin'));
  assert.equal(lin.preference.acTargetTempC, 25);
  await api.updatePreference(ctx('person-lin'), { lightBrightness: 10, acTargetTempC: 26, curtainOpenPercent: 0 });
  const plan = (await api.sendMessage({ context: ctx('person-lin'), text: '我想休息' })).plan!;
  assert.deepEqual(plan.actions.map((a) => a.value), [10, 26, 0]);
  const chen = (await api.sendMessage({ context: ctx('person-chen'), text: '我想休息' })).plan!;
  assert.deepEqual(chen.actions.map((a) => a.value), [30, 22, 10]);
  await assert.rejects(api.updatePreference(ctx('person-guest'), { lightBrightness: 10, acTargetTempC: 26, curtainOpenPercent: 0 }));

  await api.setEnergyMode(ctx('person-lin'), 'eco');
  const eco = (await api.sendMessage({ context: ctx('person-lin'), text: '我想休息' })).plan!;
  assert.equal(eco.actions[1].value, 26.5);
  assert.equal(eco.energy!.applied, true);
});

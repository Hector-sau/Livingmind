import assert from 'node:assert/strict';
import { test } from 'node:test';

import { actionOutcomeLabel, actionablePlanId, conversationReducer, greeting, resultPresentation, resultSummary, type Message } from '../features/chat/conversation';
import { sceneTimeline } from '../features/scenes/timeline';
import type { ActionExecution, ActionResult, ActivityRecord, DeviceState, Plan } from '../services/types';

const plan = (planId: string): Plan => ({
  planId,
  version: 1,
  personId: 'person-lin',
  spaceId: 's',
  scenario: 'rest',
  source: 'rule',
  summary: '',
  notes: [],
  utterance: '我想休息',
  actions: [],
  status: 'proposed',
  createdAt: '2026-09-17T12:00:00Z',
  expiresAt: '2026-09-17T12:10:00Z',
  generation: { modeRequested: 'rule', provider: null, model: null, latencyMs: 0, fallbackReason: null, goal: null },
  schedule: [],
});

test('conversations are kept per person', () => {
  const m: Message = { kind: 'user', id: '1', text: 'hi', at: '' };
  let s = conversationReducer({}, { type: 'append', personId: 'a', message: m });
  s = conversationReducer(s, { type: 'append', personId: 'b', message: { ...m, id: '2' } });
  assert.equal(s.a.length, 1);
  assert.equal(s.b.length, 1);
  assert.deepEqual(conversationReducer(s, { type: 'clearAll' }), {});
});

test('only the latest plan card that matches the current plan is actionable', () => {
  const msgs: Message[] = [
    { kind: 'plan', id: '1', plan: plan('p1'), at: '' },
    { kind: 'user', id: '2', text: 'x', at: '' },
    { kind: 'plan', id: '3', plan: plan('p2'), at: '' },
    { kind: 'system', id: '4', text: 'x', tone: 'info', at: '' },
  ];
  assert.equal(actionablePlanId(msgs, 'p2'), 'p2');
  assert.equal(actionablePlanId(msgs, 'p1'), null);
  assert.equal(actionablePlanId(msgs, null), null);
});

test('result summary and greeting wording', () => {
  const r = (outcome: 'succeeded' | 'skipped') =>
    ({ actionId: 'a', device: 'ac', command: 'set_target_temperature', value: 1, outcome, reason: null, observedValue: 1 }) as const;
  assert.equal(resultSummary([r('succeeded'), r('succeeded')]), '已完成 2 项设备调整');
  assert.equal(resultSummary([r('succeeded'), r('skipped')]), '完成 1/2 项，其余未执行');
  assert.match(greeting('访客', true), /访客模式/);
  assert.match(greeting('林悦', false), /林悦/);
});

const result = (outcome: ActionResult['outcome']): ActionResult => ({
  actionId: 'a', device: 'ac', command: 'set_target_temperature', value: 24,
  outcome, reason: null, observedValue: outcome === 'succeeded' ? 24 : null,
});

const receipt: ActionExecution = {
  source: 'plan', recoveryAttempts: 0, recoveryExhausted: false,
  actionId: 'a', planId: 'p1', spaceId: 's', serviceId: 'service', grantId: 'grant',
  serviceEpoch: 0, attemptCount: 1, device: 'ac', command: 'set_target_temperature',
  requestedAt: '', requestedValue: 24, status: 'completed', observedValue: 24,
};
const unknownMessage: Message = { kind: 'result', id: 'result-1', plan: plan('p1'),
  results: [result('unknown')], deviceState: {} as DeviceState, repeated: false, at: '' };
const receiptAction = { type: 'reconcileResult', personId: 'person-lin', messageId: 'result-1', receipt } as const;

test('reconciliation updates a matching unknown result without adding a new message', () => {
  const state = conversationReducer({ 'person-lin': [unknownMessage] }, receiptAction);
  assert.equal(state['person-lin'].length, 1);
  const m = state['person-lin'][0];
  assert.equal(m.kind, 'result');
  if (m.kind !== 'result') return;
  assert.equal(m.results[0].outcome, 'succeeded');
  assert.equal(m.results[0].observedValue, 24);
  assert.match(m.reconciliationNote!, /没有重发/);
});

test('late reconciliation cannot recreate cleared history or update another person', () => {
  assert.deepEqual(conversationReducer({}, receiptAction), {});
  const state = { 'person-lin': [unknownMessage], other: [] };
  assert.deepEqual(conversationReducer(state, { ...receiptAction, personId: 'other' }), state);
});

test('mismatched receipt scope cannot alter a result', () => {
  const state = { 'person-lin': [unknownMessage] };
  for (const change of [{ planId: 'other' }, { spaceId: 'other' }]) {
    assert.deepEqual(conversationReducer(state, { ...receiptAction, receipt: { ...receipt, ...change } }), state);
  }
});

test('unknown receipts stay unknown and terminal receipts are not overwritten', () => {
  let state = conversationReducer({ 'person-lin': [unknownMessage] }, { ...receiptAction, receipt: { ...receipt, status: 'unknown' } });
  let m = state['person-lin'][0];
  if (m.kind !== 'result') throw new Error('result expected');
  assert.equal(m.results[0].outcome, 'unknown');
  state = conversationReducer(state, receiptAction);
  state = conversationReducer(state, { ...receiptAction, receipt: { ...receipt, status: 'failed' } });
  m = state['person-lin'][0];
  if (m.kind !== 'result') throw new Error('result expected');
  assert.equal(m.results[0].outcome, 'succeeded');
});

test('late query failures cannot restore cleared messages', () => {
  assert.deepEqual(conversationReducer({}, { type: 'reconcileNote', personId: 'person-lin', messageId: 'result-1', text: 'offline' }), {});
});

test('lost receipts are unknown, not success or proof of non-execution', () => {
  const results = [result('succeeded'), result('unknown')];
  assert.equal(resultSummary(results), '完成 1/2 项，1 项结果未知');
  assert.equal(actionOutcomeLabel('unknown'), '结果未知');
  assert.deepEqual(resultPresentation(results, false), { title: '执行结果待确认', tone: 'amber' });
  assert.deepEqual(resultPresentation(results, true), { title: '已确认过此计划', tone: 'amber' });
});

test('failed readback does not imply that the device was never changed', () => {
  const results = [result('failed')];
  assert.equal(resultSummary(results), '完成 0/1 项，其余未确认完成');
  assert.equal(actionOutcomeLabel('failed'), '未确认完成');
  assert.deepEqual(resultPresentation(results, false), { title: '设备调整未全部完成', tone: 'amber' });
});

test('skipped and rejected actions never produce an all-complete presentation', () => {
  assert.equal(actionOutcomeLabel('skipped'), '已跳过');
  assert.equal(actionOutcomeLabel('rejected'), '已拒绝');
  assert.deepEqual(resultPresentation([result('skipped'), result('rejected')], false), {
    title: '设备调整未全部完成', tone: 'amber',
  });
});

test('only nonempty all-success results have a green completion presentation', () => {
  assert.equal(resultSummary([]), '没有需要执行的动作');
  assert.deepEqual(resultPresentation([], false), { title: '没有需要执行的动作', tone: 'muted' });
  assert.deepEqual(resultPresentation([result('succeeded')], false), { title: '已为你调整好', tone: 'green' });
});

const rec = (over: Partial<ActivityRecord>): ActivityRecord => ({
  activityId: Math.random().toString(),
  timestamp: '2026-09-17T14:05:00Z',
  spaceId: 's',
  kind: 'plan_created',
  source: 'system',
  message: '',
  serviceId: null,
  planId: null,
  personId: null,
  action: null,
  ...over,
});

test('scene timelines split rest actions from adjustment actions', () => {
  // newest first, as the API returns them
  const items: ActivityRecord[] = [
    rec({ kind: 'service_stopped', message: '用户停止服务' }),
    rec({ kind: 'action_executed', planId: 'adj', message: '空调设定 24°C（回读 24）' }),
    rec({ kind: 'service_adjusted', planId: 'adj', message: '自动调整（规则）：室温 28°C 高于设定 25°C，空调调整到 24°C' }),
    rec({ kind: 'event_received', message: '模拟事件：室温变为 28°C' }),
    rec({ kind: 'action_executed', planId: 'rest', message: '灯光亮度调到 15%（回读 15）' }),
    rec({ kind: 'plan_confirmed', planId: 'rest' }),
    rec({ kind: 'plan_created', planId: 'rest' }),
  ];
  const rest = sceneTimeline('scene-rest', items).map((e) => e.text);
  assert.deepEqual(rest, ['确认了休息计划', '灯光亮度调到 15%', '停止了休息服务，设备保持当前状态']);
  const temp = sceneTimeline('scene-room-temp', items).map((e) => e.text);
  assert.deepEqual(temp, ['模拟事件 · 室温变为 28°C', '自动调整：室温 28°C 高于设定 25°C，空调调整到 24°C', '空调设定 24°C']);
  assert.deepEqual(sceneTimeline('scene-wake', items), []);
});

test('scene timelines attribute actions by what started them (backend logs service actions under the rest plan)', () => {
  const items: ActivityRecord[] = [
    rec({ kind: 'service_completed', message: '07:00 唤醒完成，整晚服务结束，设备保持当前状态' }),
    rec({ kind: 'action_executed', planId: 'rest', message: '窗帘开到 100%（回读 100）' }),
    rec({ kind: 'schedule_step_executed', message: '整晚安排 07:00 唤醒 3/3：窗帘全开、灯光 60%' }),
    rec({ kind: 'clock_advanced', message: '模拟时钟 06:45 → 07:00，到点 1 步' }),
    rec({ kind: 'action_executed', planId: 'rest', message: '空调设定 24°C（回读 24）' }),
    rec({ kind: 'service_adjusted', planId: 'adj', message: '自动调整（规则）：室温 28°C 高于设定 25°C，空调调整到 24°C' }),
    rec({ kind: 'action_executed', planId: 'rest', message: '灯光亮度调到 15%（回读 15）' }),
    rec({ kind: 'plan_confirmed', planId: 'rest' }),
  ];
  assert.deepEqual(sceneTimeline('scene-rest', items).map((e) => e.text), ['确认了休息计划', '灯光亮度调到 15%']);
  assert.deepEqual(sceneTimeline('scene-room-temp', items).map((e) => e.text), [
    '自动调整：室温 28°C 高于设定 25°C，空调调整到 24°C',
    '空调设定 24°C',
  ]);
  assert.deepEqual(sceneTimeline('scene-wake', items).map((e) => e.text), [
    '模拟时间 07:00 唤醒 3/3：窗帘全开、灯光 60%',
    '07:00 唤醒完成，整晚服务结束，设备保持当前状态',
  ]);
});

import assert from 'node:assert/strict';
import { test } from 'node:test';

import { actionablePlanId, conversationReducer, greeting, resultSummary, type Message } from '../features/chat/conversation';
import { sceneTimeline } from '../features/scenes/timeline';
import type { ActivityRecord, Plan } from '../services/types';

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

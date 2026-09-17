import assert from 'node:assert/strict';
import { test } from 'node:test';

import { planBlockReason } from '../features/rest/planGate';
import type { Plan, Service } from '../services/types';

const plan = (over: Partial<Plan> = {}): Plan => ({
  planId: 'p1',
  version: 1,
  personId: 'a',
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
  ...over,
});
const now = new Date('2026-09-17T12:01:00Z');

test('proposed plan for current person can be confirmed', () => {
  assert.equal(planBlockReason(plan(), null, 'a', now), null);
});

test('blocked cases', () => {
  assert.ok(planBlockReason(null, null, 'a', now));
  assert.ok(planBlockReason(plan(), null, 'b', now));
  assert.ok(planBlockReason(plan({ status: 'executed' }), null, 'a', now));
  assert.ok(planBlockReason(plan(), null, 'a', new Date('2026-09-17T12:11:00Z')));
  assert.ok(planBlockReason(plan({ status: 'invalidated' }), null, 'a', now));
  const svc = { status: 'active' } as Service;
  assert.ok(planBlockReason(plan(), svc, 'a', now));
});

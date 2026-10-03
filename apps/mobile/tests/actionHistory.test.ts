import assert from 'node:assert/strict';
import { test } from 'node:test';
import { actionStatus, mergeReceipt, scopedActions } from '../features/activity/actionHistoryRules';
import { controlResultMessage } from '../features/devices/control';
import type { ActionExecution } from '../services/types';

const ctx = { accountId: 'account', personId: 'person', spaceId: 'space' };
const item: ActionExecution = { ...ctx, actionId: 'a', grantId: null, planId: null, serviceId: null,
  source: 'manual', device: 'light', command: 'set_brightness', requestedValue: 20, serviceEpoch: 1,
  status: 'unknown', attemptCount: 1, requestedAt: '2026-10-03T00:00:00Z', recoveryAttempts: 1, recoveryExhausted: false };

test('action history rejects another person, account or space', () => {
  assert.deepEqual(scopedActions([item, { ...item, personId: 'other' }, { ...item, accountId: 'other' },
    { ...item, spaceId: 'other' }], ctx), [item]);
});
test('unknown exhausted action is not displayed as failed or completed', () => {
  assert.match(actionStatus({ ...item, recoveryExhausted: true }), /未知.*暂停/);
  assert.doesNotMatch(actionStatus(item), /失败|完成/);
});
test('a matching receipt updates a manual action with no plan', () => {
  const done = { ...item, status: 'completed' as const };
  assert.deepEqual(mergeReceipt([item], done), [done]);
  assert.deepEqual(mergeReceipt([done], item), [done]);
});
test('a receipt cannot insert a cleared action or modify another person', () => {
  assert.deepEqual(mergeReceipt([], item), []);
  assert.deepEqual(mergeReceipt([item], { ...item, personId: 'other', status: 'completed' }), [item]);
});
test('uncertain manual result asks for reconciliation, never a retry', () => {
  const text = controlResultMessage({ actionId: 'a', device: 'light', command: 'set_brightness', value: 20,
    outcome: 'unknown', observedValue: null, reason: null });
  assert.match(text!, /待核对/);
  assert.doesNotMatch(text!, /点击重试|已完成/);
});

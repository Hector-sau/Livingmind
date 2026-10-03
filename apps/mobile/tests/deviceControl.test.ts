import assert from 'node:assert/strict';
import { test } from 'node:test';

import { createMockApi } from '../services/mock/mockApi';

/**
 * The front-end mock and the backend must answer the same way, or switching modes
 * silently changes what the demo proves. These mirror backend/tests/test_device_control.py.
 */
const SPACE = 'space-home-bedroom';

function setup() {
  const api = createMockApi({ latencyMs: 0 });
  const ctx = { accountId: 'demo-account', personId: 'person-lin', spaceId: SPACE };
  return { api, ctx, space: SPACE };
}

test('a control executes at once and offers an undo back to the previous value', async () => {
  const { api, ctx, space } = setup();
  const before = (await api.getDeviceState(space)).lightBrightness;

  const res = await api.controlDevice(space, { context: ctx, device: 'light', value: 20 });
  assert.equal(res.result.outcome, 'succeeded');
  assert.ok(res.deviceState);
  assert.equal(res.deviceState.lightBrightness, 20);
  assert.ok(res.undo);
  assert.equal(res.undo?.previousValue, before);
  assert.equal(res.undo?.appliedValue, 20);
});

test('undo restores the exact previous value, not a guessed opposite', async () => {
  const { api, ctx, space } = setup();
  await api.controlDevice(space, { context: ctx, device: 'light', value: 30 });
  const off = await api.controlDevice(space, { context: ctx, device: 'light', value: 0 });
  assert.equal((await api.getDeviceState(space)).lightBrightness, 0);

  const undone = await api.undoDeviceControl(off.undo!.undoId, { context: ctx });
  assert.equal(undone.restoredValue, 30);
  assert.ok(undone.deviceState);
  assert.equal(undone.deviceState.lightBrightness, 30, 'undoing "off" must not jump to full brightness');
});

test('an undo can only be used once', async () => {
  const { api, ctx, space } = setup();
  await api.controlDevice(space, { context: ctx, device: 'light', value: 60 });
  const res = await api.controlDevice(space, { context: ctx, device: 'light', value: 15 });

  await api.undoDeviceControl(res.undo!.undoId, { context: ctx });
  await assert.rejects(() => api.undoDeviceControl(res.undo!.undoId, { context: ctx }), /撤销窗口/);
  assert.equal((await api.getDeviceState(space)).lightBrightness, 60);
});

test('a newer control supersedes the older offer', async () => {
  const { api, ctx, space } = setup();
  const first = await api.controlDevice(space, { context: ctx, device: 'light', value: 70 });
  const second = await api.controlDevice(space, { context: ctx, device: 'light', value: 25 });

  await assert.rejects(() => api.undoDeviceControl(first.undo!.undoId, { context: ctx }));
  const undone = await api.undoDeviceControl(second.undo!.undoId, { context: ctx });
  assert.ok(undone.deviceState);
  assert.equal(undone.deviceState.lightBrightness, 70);
});

test('a reset leaves nothing to undo', async () => {
  const { api, ctx, space } = setup();
  const res = await api.controlDevice(space, { context: ctx, device: 'light', value: 35 });
  await api.resetDemo();
  await assert.rejects(() => api.undoDeviceControl(res.undo!.undoId, { context: ctx }));
});

test('the same whitelist and ranges apply as on the backend', async () => {
  const { api, ctx, space } = setup();
  const tooCold = await api.controlDevice(space, { context: ctx, device: 'ac', value: 5 });
  assert.equal(tooCold.result.outcome, 'rejected');
  assert.match(tooCold.result.reason ?? '', /范围/);
  assert.equal(tooCold.undo, null, 'a refused write has nothing to undo');

  const fractional = await api.controlDevice(space, { context: ctx, device: 'light', value: 20.5 });
  assert.equal(fractional.result.outcome, 'rejected');
  assert.equal(fractional.undo, null);
});

test('a write that changes nothing offers no undo', async () => {
  const { api, ctx, space } = setup();
  await api.controlDevice(space, { context: ctx, device: 'light', value: 40 });
  const again = await api.controlDevice(space, { context: ctx, device: 'light', value: 40 });
  assert.equal(again.result.outcome, 'succeeded');
  assert.equal(again.undo, null);
});

test('control and undo are both recorded, with the mock labelled as the source', async () => {
  const { api, ctx, space } = setup();
  const res = await api.controlDevice(space, { context: ctx, device: 'curtain', value: 40 });
  await api.undoDeviceControl(res.undo!.undoId, { context: ctx });

  const items = (await api.getActivity(space)).items;
  const kinds = items.map((i) => i.kind);
  assert.ok(kinds.includes('device_controlled'));
  assert.ok(kinds.includes('device_control_undone'));
  assert.ok(items.every((i) => i.source === 'frontend_mock'), 'mock activity must stay labelled');
});

test('a mismatched context is refused', async () => {
  const { api, ctx, space } = setup();
  await assert.rejects(
    () => api.controlDevice(space, { context: { ...ctx, spaceId: 'space-other' }, device: 'light', value: 10 }),
    /空间/,
  );
});

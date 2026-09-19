import assert from 'node:assert/strict';
import { test } from 'node:test';

import {
  DEVICE_RANGE,
  clampValue,
  formatValue,
  ratioFromValue,
  sliderView,
  snapValue,
  tileInteractive,
  undoExpired,
  undoSecondsLeft,
  valueFromRatio,
} from '../features/devices/control';

test('a drag can never produce a value the backend would refuse', () => {
  // Light and curtain are integer-only on the backend; AC allows halves.
  for (const ratio of [0, 0.017, 0.333, 0.5, 0.666, 0.999, 1]) {
    const light = valueFromRatio('light', ratio);
    assert.ok(Number.isInteger(light), `light ${light} must be whole`);
    assert.ok(light >= 0 && light <= 100);

    const ac = valueFromRatio('ac', ratio);
    assert.ok(ac >= 16 && ac <= 30);
    assert.equal(Math.round(ac * 2) / 2, ac, `AC ${ac} must land on a half degree`);
  }
});

test('ratios outside the track are clamped rather than extrapolated', () => {
  assert.equal(valueFromRatio('light', -3), 0, 'dragging past the left edge stops at the minimum');
  assert.equal(valueFromRatio('light', 42), 100);
  assert.equal(clampValue('ac', 4), 16);
  assert.equal(clampValue('ac', 99), 30);
  assert.equal(clampValue('light', Number.NaN), 0);
});

test('snapping does not leave binary drift behind', () => {
  // 16 + 9 * 0.5 is 20.5 in decimal but 20.499999999999996 in floating point.
  assert.equal(snapValue('ac', 20.5), 20.5);
  assert.equal(snapValue('ac', 20.4), 20.5);
  assert.equal(snapValue('ac', 20.1), 20);
  assert.equal(String(valueFromRatio('ac', 9 / 28)), '20.5');
});

test('value and ratio round-trip', () => {
  for (const device of ['light', 'ac', 'curtain'] as const) {
    const { min, max } = DEVICE_RANGE[device];
    for (const value of [min, (min + max) / 2, max]) {
      const snapped = snapValue(device, value);
      assert.equal(valueFromRatio(device, ratioFromValue(device, snapped)), snapped);
    }
  }
});

test('a finger on the track beats anything the backend pushes', () => {
  // The person has dragged to 20 while the device still reports 80.
  const dragging = sliderView('light', { local: 20, readback: 80, pending: null });
  assert.equal(dragging.target, 20, 'the handle must not jump back to the server value mid-drag');
  assert.equal(dragging.actual, 80);
  assert.ok(dragging.settling);
});

test('after the finger lifts, the sent value holds the handle until it is read back', () => {
  const sent = sliderView('light', { local: null, readback: 80, pending: 20 });
  assert.equal(sent.target, 20);
  assert.equal(sent.actual, 80);
  assert.ok(sent.settling, 'the gap is the work still in flight');

  const settled = sliderView('light', { local: null, readback: 20, pending: 20 });
  assert.equal(settled.target, 20);
  assert.equal(settled.actual, 20);
  assert.equal(settled.settling, false);
});

test('with nothing local or pending, the device read-back is the truth', () => {
  const view = sliderView('ac', { local: null, readback: 26, pending: null });
  assert.equal(view.target, 26);
  assert.equal(view.actual, 26);
  assert.equal(view.settling, false);
});

test('the undo countdown is whole seconds and never goes negative', () => {
  const now = Date.parse('2026-09-19T10:00:00.000Z');
  const in5s = '2026-09-19T10:00:05.000Z';
  assert.equal(undoSecondsLeft(in5s, now), 5);
  assert.equal(undoSecondsLeft(in5s, now + 4_200), 1);
  assert.equal(undoSecondsLeft(in5s, now + 5_000), 0);
  assert.equal(undoSecondsLeft(in5s, now + 60_000), 0);
  assert.equal(undoSecondsLeft('not a date', now), 0);
});

test('an expired or unparseable window is treated as closed', () => {
  const now = Date.parse('2026-09-19T10:00:00.000Z');
  assert.equal(undoExpired('2026-09-19T10:00:05.000Z', now), false);
  assert.equal(undoExpired('2026-09-19T10:00:00.000Z', now), true);
  assert.equal(undoExpired('nonsense', now), true, 'a window we cannot read is not an open window');
});

test('a tile in flight or offline refuses touches', () => {
  assert.equal(tileInteractive('idle'), true);
  assert.equal(tileInteractive('failed'), true, 'a failed write can be retried');
  assert.equal(tileInteractive('busy'), false);
  assert.equal(tileInteractive('offline'), false);
});

test('values are formatted with the unit the device actually uses', () => {
  assert.equal(formatValue('light', 20), '20%');
  assert.equal(formatValue('ac', 24.5), '24.5°C');
  assert.equal(formatValue('curtain', 0), '0%');
});

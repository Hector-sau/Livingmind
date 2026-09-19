// Pure rules behind the controllable device tiles. No React, so they unit-test directly.
//
// The dual-track rule lives here: while a finger is down the slider shows the local
// value and ignores anything the backend pushes; the moment it lifts, the server's
// read-back value is the truth again. Without this, every device refresh yanks the
// handle out from under the person dragging it.

import type { DeviceType } from '../../services/types';

export interface DeviceRange {
  readonly min: number;
  readonly max: number;
  /** Smallest change the device accepts. Mirrors the backend whitelist. */
  readonly step: number;
  readonly unit: string;
}

/** Same bounds the backend executor enforces; a mismatch here shows up as a rejected write. */
export const DEVICE_RANGE: Record<DeviceType, DeviceRange> = {
  light: { min: 0, max: 100, step: 1, unit: '%' },
  ac: { min: 16, max: 30, step: 0.5, unit: '°C' },
  curtain: { min: 0, max: 100, step: 1, unit: '%' },
};

export function clampValue(device: DeviceType, value: number): number {
  const { min, max } = DEVICE_RANGE[device];
  if (!Number.isFinite(value)) return min;
  return value < min ? min : value > max ? max : value;
}

/** Snap to the device's step so a drag can never produce a value the backend refuses. */
export function snapValue(device: DeviceType, value: number): number {
  const { min, step } = DEVICE_RANGE[device];
  const snapped = min + Math.round((clampValue(device, value) - min) / step) * step;
  // Guard against binary drift: 16 + 9 * 0.5 must be 20.5, not 20.499999999999996.
  return Math.round(snapped * 100) / 100;
}

/** A touch at `ratio` (0 = left edge, 1 = right edge) becomes a device value. */
export function valueFromRatio(device: DeviceType, ratio: number): number {
  const { min, max } = DEVICE_RANGE[device];
  const bounded = ratio < 0 ? 0 : ratio > 1 ? 1 : ratio;
  return snapValue(device, min + bounded * (max - min));
}

/** Where a value sits on the track, 0..1. */
export function ratioFromValue(device: DeviceType, value: number): number {
  const { min, max } = DEVICE_RANGE[device];
  if (max === min) return 0;
  return (clampValue(device, value) - min) / (max - min);
}

export function formatValue(device: DeviceType, value: number): string {
  const { unit } = DEVICE_RANGE[device];
  const text = Number.isInteger(value) ? `${value}` : `${value}`;
  return `${text}${unit}`;
}

/**
 * What the slider should draw.
 *
 * `target` is the handle (what the person asked for), `actual` is the small marker
 * (what the device reported). When they differ the gap between them is the work the
 * system is still doing — the one piece of information the old read-only panel threw away.
 */
export interface SliderView {
  readonly target: number;
  readonly actual: number;
  /** True when the device has not reached the target yet. */
  readonly settling: boolean;
}

export function sliderView(
  device: DeviceType,
  opts: { local: number | null; readback: number; pending: number | null },
): SliderView {
  // A finger on the track wins over everything: the person is looking at their own drag.
  if (opts.local !== null) {
    return { target: opts.local, actual: opts.readback, settling: opts.local !== opts.readback };
  }
  // Between "sent" and "read back", the handle stays where the person put it.
  const target = opts.pending ?? opts.readback;
  return { target, actual: opts.readback, settling: clampValue(device, target) !== clampValue(device, opts.readback) };
}

/** Whole seconds left in an undo window; never negative. */
export function undoSecondsLeft(expiresAtIso: string, nowMs: number): number {
  const expires = Date.parse(expiresAtIso);
  if (!Number.isFinite(expires)) return 0;
  return Math.max(0, Math.ceil((expires - nowMs) / 1000));
}

export function undoExpired(expiresAtIso: string, nowMs: number): boolean {
  const expires = Date.parse(expiresAtIso);
  if (!Number.isFinite(expires)) return true;
  return nowMs >= expires;
}

export type TileStatus = 'idle' | 'busy' | 'failed' | 'offline';

/** One place that decides whether a tile accepts touches. */
export function tileInteractive(status: TileStatus): boolean {
  return status === 'idle' || status === 'failed';
}

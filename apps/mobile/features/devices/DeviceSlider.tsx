import { useMemo, useRef, useState } from 'react';
import { Animated, LayoutChangeEvent, PanResponder, StyleSheet, View } from 'react-native';

import type { DeviceType } from '../../services/types';
import { colors, radius } from '../../theme/tokens';
import { ratioFromValue, sliderView, valueFromRatio } from './control';

interface Props {
  device: DeviceType;
  /** Latest value read back from the device. */
  readback: number;
  /** Value already sent and not yet confirmed, if any. */
  pending: number | null;
  disabled: boolean;
  color: string;
  fill: string;
  /** Called continuously while dragging, for the big number above the track. */
  onPreview: (value: number | null) => void;
  /** Called once, when the finger lifts. This is the only call that writes a device. */
  onCommit: (value: number) => void;
  label: string;
}

const TRACK_HEIGHT = 48;
const HANDLE = 36;

/**
 * One continuous device control.
 *
 * Dragging updates a local value only; the write happens on release. A gesture the
 * parent steals (a scroll, a modal) rolls back to the value at touch-down rather than
 * leaving the device somewhere nobody chose.
 */
export function DeviceSlider({
  device,
  readback,
  pending,
  disabled,
  color,
  fill,
  onPreview,
  onCommit,
  label,
}: Props) {
  const [width, setWidth] = useState(0);
  const [local, setLocal] = useState<number | null>(null);
  // Refs, not state: the responder callbacks are created once and must not close over
  // a stale render's values.
  const widthRef = useRef(0);
  const localRef = useRef<number | null>(null);
  const snapshotRef = useRef(readback);
  const disabledRef = useRef(disabled);
  disabledRef.current = disabled;

  const setLocalValue = (value: number | null) => {
    localRef.current = value;
    setLocal(value);
    onPreview(value);
  };

  const valueAt = (x: number): number => {
    const w = widthRef.current;
    if (w <= 0) return readback;
    // Measure from the centre of the handle so the value under the finger is the one shown.
    const usable = Math.max(1, w - HANDLE);
    return valueFromRatio(device, (x - HANDLE / 2) / usable);
  };

  const responder = useMemo(
    () =>
      PanResponder.create({
        onStartShouldSetPanResponder: () => !disabledRef.current,
        onMoveShouldSetPanResponder: () => !disabledRef.current,
        onPanResponderGrant: (evt) => {
          if (disabledRef.current) return;
          snapshotRef.current = pendingOrReadback();
          setLocalValue(valueAt(evt.nativeEvent.locationX));
        },
        onPanResponderMove: (evt, gesture) => {
          if (disabledRef.current) return;
          // locationX is unreliable once the finger leaves the element, so track by page
          // position relative to where the gesture started.
          const startX = evt.nativeEvent.locationX - gesture.dx;
          setLocalValue(valueAt(startX + gesture.dx));
        },
        onPanResponderRelease: () => {
          const value = localRef.current;
          setLocalValue(null);
          if (value !== null && !disabledRef.current) onCommit(value);
        },
        onPanResponderTerminate: () => {
          // The gesture was taken away mid-drag: put the handle back, write nothing.
          setLocalValue(null);
        },
      }),
    // Created once; everything it needs is read from refs.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  );

  function pendingOrReadback(): number {
    return pending ?? readback;
  }

  const view = sliderView(device, { local, readback, pending });
  const targetRatio = ratioFromValue(device, view.target);
  const actualRatio = ratioFromValue(device, view.actual);
  const usable = Math.max(0, width - HANDLE);
  const targetX = usable * targetRatio;
  const actualX = usable * actualRatio + HANDLE / 2;
  const gapLeft = Math.min(targetX + HANDLE / 2, actualX);
  const gapWidth = Math.abs(actualX - (targetX + HANDLE / 2));

  const onLayout = (e: LayoutChangeEvent) => {
    const w = e.nativeEvent.layout.width;
    widthRef.current = w;
    setWidth(w);
  };

  return (
    <View
      onLayout={onLayout}
      style={[styles.track, disabled && styles.trackDisabled]}
      accessibilityRole="adjustable"
      accessibilityLabel={label}
      accessibilityValue={{ min: 0, max: 100, now: Math.round(targetRatio * 100) }}
      testID={`device-slider-${device}`}
      {...responder.panHandlers}
    >
      <Animated.View style={[styles.fill, { width: targetX + HANDLE / 2, backgroundColor: fill }]} />
      {view.settling && width > 0 ? (
        <View style={[styles.gap, { left: gapLeft, width: gapWidth, backgroundColor: color, opacity: 0.28 }]} />
      ) : null}
      {/* The handle is hidden while the device is unreachable: an empty track says
          "no control here" more plainly than a greyed-out knob. */}
      {disabled ? null : (
        <View style={[styles.handle, { left: targetX, borderColor: color }]} testID={`device-handle-${device}`} />
      )}
      {view.settling && width > 0 ? (
        <View style={[styles.actual, { left: actualX - 5 }]} testID={`device-actual-${device}`} />
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  track: {
    height: TRACK_HEIGHT,
    borderRadius: TRACK_HEIGHT / 2,
    backgroundColor: '#E3EDF5',
    justifyContent: 'center',
    overflow: 'hidden',
  },
  trackDisabled: { backgroundColor: '#E9EEF3' },
  fill: { position: 'absolute', left: 0, top: 0, bottom: 0, borderRadius: TRACK_HEIGHT / 2 },
  gap: { position: 'absolute', top: 0, bottom: 0 },
  handle: {
    position: 'absolute',
    width: HANDLE,
    height: HANDLE,
    borderRadius: HANDLE / 2,
    backgroundColor: colors.card,
    borderWidth: 2.5,
    boxShadow: '0px 3px 8px rgba(15,42,61,0.18)',
  },
  actual: {
    position: 'absolute',
    width: 10,
    height: 10,
    borderRadius: 5,
    backgroundColor: colors.navy,
    borderWidth: 2,
    borderColor: colors.card,
  },
});

export const SLIDER_TRACK_HEIGHT = TRACK_HEIGHT;
export const SLIDER_HANDLE = HANDLE;
export const SLIDER_RADIUS = radius.pill;

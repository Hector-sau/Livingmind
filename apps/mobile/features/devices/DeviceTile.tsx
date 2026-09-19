import { useEffect, useRef, useState } from 'react';
import { Animated, Pressable, StyleSheet, Text, View } from 'react-native';

import { DeviceIcon } from '../../components/Icon';
import { NATIVE_DRIVER, useReducedMotion } from '../../components/motion';
import type { DeviceType } from '../../services/types';
import { colors, font, radius, space } from '../../theme/tokens';
import { DEVICE_RANGE, formatValue, sliderView, tileInteractive, type TileStatus } from './control';
import { DeviceSlider } from './DeviceSlider';

export interface DeviceLook {
  name: string;
  color: string;
  tint: string;
  fill: string;
}

export const DEVICE_LOOK: Record<DeviceType, DeviceLook> = {
  light: { name: '灯光', color: '#B7791F', tint: colors.amberTint, fill: '#F7E2B5' },
  ac: { name: '空调', color: colors.blue, tint: colors.homeTint, fill: '#BFE6FB' },
  curtain: { name: '窗帘', color: '#0E7C7D', tint: colors.tealTint, fill: '#BEEDED' },
};

interface Props {
  device: DeviceType;
  readback: number;
  pending: number | null;
  status: TileStatus;
  failureReason: string | null;
  compact?: boolean;
  onControl: (value: number) => void;
  /** Tapping the icon toggles between the device's two ends. */
  onToggle: () => void;
}

/**
 * One device, directly controllable.
 *
 * The icon is its own touch target (tap = toggle) so the common action costs one tap,
 * while the track underneath handles everything in between. A successful write pulses
 * the icon twice — short, self-resetting, and enough to tell the person it landed.
 */
export function DeviceTile({
  device,
  readback,
  pending,
  status,
  failureReason,
  compact,
  onControl,
  onToggle,
}: Props) {
  const look = DEVICE_LOOK[device];
  const [preview, setPreview] = useState<number | null>(null);
  const view = sliderView(device, { local: preview, readback, pending });
  const interactive = tileInteractive(status);
  const offline = status === 'offline';
  const reduced = useReducedMotion();

  const pulse = useRef(new Animated.Value(0)).current;
  const lastSettled = useRef(readback);
  useEffect(() => {
    if (readback === lastSettled.current) return;
    lastSettled.current = readback;
    if (reduced) return;
    pulse.setValue(0);
    Animated.sequence([
      Animated.timing(pulse, { toValue: 1, duration: 130, useNativeDriver: NATIVE_DRIVER }),
      Animated.timing(pulse, { toValue: 0, duration: 130, useNativeDriver: NATIVE_DRIVER }),
      Animated.timing(pulse, { toValue: 1, duration: 130, useNativeDriver: NATIVE_DRIVER }),
      Animated.timing(pulse, { toValue: 0, duration: 130, useNativeDriver: NATIVE_DRIVER }),
    ]).start();
  }, [readback, pulse, reduced]);

  const scale = pulse.interpolate({ inputRange: [0, 1], outputRange: [1, 1.12] });

  const subtitle = (() => {
    if (offline) return '离线 · 数值可能已过期';
    if (status === 'failed') return failureReason ?? '操作失败，点击重试';
    if (status === 'busy') return `正在调整…实测 ${formatValue(device, view.actual)}`;
    if (view.settling) return `目标 ${formatValue(device, view.target)} · 实测 ${formatValue(device, view.actual)}`;
    return `目标 ${formatValue(device, view.target)} · 实测 ${formatValue(device, view.actual)} · 已同步`;
  })();

  return (
    <View
      style={[
        styles.tile,
        compact && styles.tileCompact,
        offline && styles.tileOffline,
        status === 'failed' && styles.tileFailed,
      ]}
      testID={`device-tile-${device}`}
    >
      <View style={styles.head}>
        <Pressable
          onPress={onToggle}
          disabled={!interactive}
          accessibilityRole="button"
          accessibilityLabel={`${look.name}开关`}
          testID={`device-toggle-${device}`}
          style={({ pressed }) => [styles.iconBtn, { backgroundColor: look.tint }, pressed && styles.iconPressed]}
        >
          <Animated.View style={{ transform: [{ scale }] }}>
            <DeviceIcon device={device} size={compact ? 20 : 24} color={offline ? colors.muted : look.color} />
          </Animated.View>
          {offline ? (
            <View style={styles.badge} testID={`device-offline-${device}`}>
              <Text style={styles.badgeText}>!</Text>
            </View>
          ) : null}
        </Pressable>

        <View style={styles.meta}>
          <Text style={[styles.name, compact && styles.nameCompact]}>{look.name}</Text>
          <Text style={[styles.sub, status === 'failed' && styles.subFailed]} numberOfLines={1}>
            {subtitle}
          </Text>
        </View>

        <Text style={[styles.value, compact && styles.valueCompact]} testID={`device-value-${device}`}>
          {formatValue(device, view.target)}
        </Text>
      </View>

      <DeviceSlider
        device={device}
        readback={readback}
        pending={pending}
        disabled={!interactive}
        color={look.color}
        fill={look.fill}
        label={`${look.name}，${DEVICE_RANGE[device].min} 到 ${DEVICE_RANGE[device].max}`}
        onPreview={setPreview}
        onCommit={onControl}
      />

      {status === 'busy' ? <View style={styles.progressTrack} testID={`device-busy-${device}`} /> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  tile: {
    backgroundColor: colors.card,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.lg,
    padding: space.md,
    gap: space.md,
    overflow: 'hidden',
  },
  tileCompact: { padding: space.sm + 2, gap: space.sm },
  tileOffline: { opacity: 0.45 },
  tileFailed: { borderColor: colors.red, borderWidth: 2 },
  head: { flexDirection: 'row', alignItems: 'center', gap: space.md },
  iconBtn: { width: 48, height: 48, borderRadius: 24, alignItems: 'center', justifyContent: 'center' },
  iconPressed: { opacity: 0.7 },
  badge: {
    position: 'absolute',
    right: -2,
    bottom: -2,
    width: 18,
    height: 18,
    borderRadius: 9,
    backgroundColor: colors.amber,
    borderWidth: 2,
    borderColor: colors.card,
    alignItems: 'center',
    justifyContent: 'center',
  },
  badgeText: { color: colors.card, fontSize: 10, fontWeight: '900', lineHeight: 12 },
  meta: { flex: 1, minWidth: 0 },
  name: { fontSize: font.section - 1, fontWeight: '800', color: colors.ink },
  nameCompact: { fontSize: font.body },
  sub: { fontSize: font.caption, color: colors.muted, marginTop: 2 },
  subFailed: { color: colors.red, fontWeight: '700' },
  value: { fontSize: 28, fontWeight: '800', color: colors.ink, letterSpacing: -0.6 },
  valueCompact: { fontSize: 22 },
  progressTrack: { position: 'absolute', left: 0, right: 0, bottom: 0, height: 3, backgroundColor: colors.blue, opacity: 0.35 },
});

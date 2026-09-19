import { StyleSheet, Text, View } from 'react-native';

import { Button } from '../../components/Button';
import { Card } from '../../components/Card';
import { EmptyState } from '../../components/EmptyState';
import { Pill } from '../../components/Pill';
import type { DeviceState, DeviceType, UndoWindow } from '../../services/types';
import { colors, font, space } from '../../theme/tokens';
import { formatTime } from '../../utils/format';
import { DEVICE_RANGE, type TileStatus } from './control';
import { DeviceTile } from './DeviceTile';
import { UndoBar } from './UndoBar';

interface Props {
  state: DeviceState | null;
  stale: boolean;
  loading: boolean;
  disabled: boolean;
  /** Values sent and not yet read back, keyed by device. */
  pending: Partial<Record<DeviceType, number>>;
  /** Reason the last direct write was refused, keyed by device. */
  failures: Partial<Record<DeviceType, string>>;
  undoWindow: UndoWindow | null;
  undoBusy: boolean;
  onRefresh: () => void;
  onControl: (device: DeviceType, value: number) => void;
  onUndo: () => void;
  onUndoExpired: () => void;
  /** Stack tiles vertically (narrow side panel). */
  vertical?: boolean;
}

const DEVICES: DeviceType[] = ['light', 'ac', 'curtain'];

function readValue(state: DeviceState, device: DeviceType): number {
  if (device === 'light') return state.lightBrightness;
  if (device === 'ac') return state.acTargetTempC;
  return state.curtainOpenPercent;
}

/** Tapping the icon flips between the two ends of the device's range. */
function toggleValue(device: DeviceType, current: number): number {
  const { min, max } = DEVICE_RANGE[device];
  if (device === 'ac') return current <= (min + max) / 2 ? max : min;
  return current > min ? min : max;
}

export function DevicePanel({
  state,
  stale,
  loading,
  disabled,
  pending,
  failures,
  undoWindow,
  undoBusy,
  onRefresh,
  onControl,
  onUndo,
  onUndoExpired,
  vertical,
}: Props) {
  const virtual = state?.source === 'virtual_device';

  const statusFor = (device: DeviceType): TileStatus => {
    // A state we could not refresh is a device we should not pretend to control.
    if (stale || disabled) return 'offline';
    if (pending[device] !== undefined) return 'busy';
    if (failures[device]) return 'failed';
    return 'idle';
  };

  return (
    <Card
      title="设备状态"
      icon="home-outline"
      right={state ? <Pill label={virtual ? '后端虚拟设备' : '前端模拟设备'} tone={virtual ? 'violet' : 'amber'} /> : null}
    >
      {stale ? <Text style={styles.stale}>无法确认最新状态：以下数值可能已过期，暂不可控制。</Text> : null}
      {!state ? (
        <EmptyState compact icon="home-outline" title="暂无设备数据" />
      ) : (
        <>
          <View style={vertical ? styles.column : styles.grid}>
            {DEVICES.map((device) => (
              <View key={device} style={vertical ? undefined : styles.gridItem}>
                <DeviceTile
                  device={device}
                  readback={readValue(state, device)}
                  pending={pending[device] ?? null}
                  status={statusFor(device)}
                  failureReason={failures[device] ?? null}
                  compact={vertical}
                  onControl={(value) => onControl(device, value)}
                  onToggle={() => onControl(device, toggleValue(device, readValue(state, device)))}
                />
              </View>
            ))}
          </View>
          <UndoBar window={undoWindow} busy={undoBusy} onUndo={onUndo} onExpire={onUndoExpired} />
          <Text style={styles.muted}>
            版本 {state.version} · {formatTime(state.updatedAt)} 更新 · 均为模拟设备，不代表真实硬件
          </Text>
        </>
      )}
      <Button label="刷新状态" icon="refresh-outline" variant="ghost" compact onPress={onRefresh} loading={loading} disabled={disabled} />
    </Card>
  );
}

const styles = StyleSheet.create({
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: space.md },
  gridItem: { flexGrow: 1, flexBasis: 240 },
  column: { gap: space.sm },
  muted: { fontSize: font.caption, color: colors.muted },
  stale: { fontSize: font.small, color: colors.amber, fontWeight: '700' },
});

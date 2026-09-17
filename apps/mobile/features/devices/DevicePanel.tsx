import { StyleSheet, Text, View } from 'react-native';

import { Button } from '../../components/Button';
import { Card } from '../../components/Card';
import { EmptyState } from '../../components/EmptyState';
import { DeviceIcon, type DeviceKind } from '../../components/Icon';
import { AnimatedBar } from '../../components/motion';
import { Pill } from '../../components/Pill';
import type { DeviceState } from '../../services/types';
import { colors, font, radius, space } from '../../theme/tokens';
import { formatTime } from '../../utils/format';

interface Props {
  state: DeviceState | null;
  stale: boolean;
  loading: boolean;
  disabled: boolean;
  onRefresh: () => void;
  /** Stack tiles vertically (narrow side panel). */
  vertical?: boolean;
}

const LOOK: Record<DeviceKind, { name: string; color: string; tint: string }> = {
  light: { name: '灯光', color: '#E0A526', tint: '#FEF6E4' },
  ac: { name: '空调', color: colors.sky, tint: colors.homeTint },
  curtain: { name: '窗帘', color: colors.teal, tint: colors.tealTint },
};

function Tile({ device, value, ratio, row }: { device: DeviceKind; value: string; ratio: number; row?: boolean }) {
  const look = LOOK[device];
  return (
    <View style={[styles.tile, row ? styles.tileRow : styles.tileGrid]}>
      <View style={styles.tileHead}>
        <View style={[styles.iconCircle, { backgroundColor: look.tint }]}>
          <DeviceIcon device={device} size={18} color={look.color} />
        </View>
        <Text style={styles.tileName}>{look.name}</Text>
      </View>
      <Text style={styles.tileValue}>{value}</Text>
      <AnimatedBar ratio={ratio} color={look.color} track="#EAF2F8" />
    </View>
  );
}

export function DevicePanel({ state, stale, loading, disabled, onRefresh, vertical }: Props) {
  const virtual = state?.source === 'virtual_device';
  return (
    <Card
      title="设备状态"
      icon="home-outline"
      right={state ? <Pill label={virtual ? '后端虚拟设备' : '前端模拟设备'} tone={virtual ? 'violet' : 'amber'} /> : null}
    >
      {stale ? <Text style={styles.stale}>无法确认最新状态：以下数值可能已过期。</Text> : null}
      {!state ? (
        <EmptyState compact icon="home-outline" title="暂无设备数据" />
      ) : (
        <>
          <View style={[vertical ? styles.column : styles.grid, stale && styles.dim]}>
            <Tile row={vertical} device="light" value={`${state.lightBrightness}%`} ratio={state.lightBrightness / 100} />
            <Tile row={vertical} device="ac" value={`${state.acTargetTempC}°C`} ratio={(state.acTargetTempC - 16) / 14} />
            <Tile row={vertical} device="curtain" value={`${state.curtainOpenPercent}%`} ratio={state.curtainOpenPercent / 100} />
          </View>
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
  column: { gap: space.sm },
  dim: { opacity: 0.45 },
  tileGrid: { flexGrow: 1, flexBasis: 140 },
  tileRow: { paddingVertical: space.sm },
  tile: {
    backgroundColor: colors.skyMist,
    borderRadius: radius.md,
    padding: space.md,
    gap: space.sm,
  },
  tileHead: { flexDirection: 'row', alignItems: 'center', gap: space.sm },
  iconCircle: { width: 32, height: 32, borderRadius: 16, alignItems: 'center', justifyContent: 'center' },
  tileName: { fontSize: font.small, color: colors.muted, fontWeight: '600' },
  tileValue: { fontSize: 26, fontWeight: '800', color: colors.ink, letterSpacing: -0.5 },
  muted: { fontSize: font.caption, color: colors.muted },
  stale: { fontSize: font.small, color: colors.amber, fontWeight: '700' },
});

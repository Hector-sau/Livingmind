import { StyleSheet, Text, View } from 'react-native';

import { Button } from '../../components/Button';
import { Card } from '../../components/Card';
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
}

function Tile({ name, value, ratio }: { name: string; value: string; ratio: number }) {
  return (
    <View style={styles.tile}>
      <Text style={styles.tileName}>{name}</Text>
      <Text style={styles.tileValue}>{value}</Text>
      <View style={styles.track}>
        <View style={[styles.fill, { width: `${Math.max(0, Math.min(1, ratio)) * 100}%` }]} />
      </View>
    </View>
  );
}

export function DevicePanel({ state, stale, loading, disabled, onRefresh }: Props) {
  const source = state?.source === 'virtual_device' ? '后端虚拟设备' : '前端模拟设备';
  return (
    <Card title="设备状态" right={state ? <Pill label={source} tone={state.source === 'virtual_device' ? 'violet' : 'amber'} /> : null}>
      {stale ? <Text style={styles.stale}>无法确认最新状态：以下数值可能已过期。</Text> : null}
      {!state ? (
        <Text style={styles.muted}>暂无设备数据。</Text>
      ) : (
        <>
          <View style={[styles.grid, stale && styles.dim]}>
            <Tile name="灯光亮度" value={`${state.lightBrightness}%`} ratio={state.lightBrightness / 100} />
            <Tile name="空调设定" value={`${state.acTargetTempC}°C`} ratio={(state.acTargetTempC - 16) / 14} />
            <Tile name="窗帘开度" value={`${state.curtainOpenPercent}%`} ratio={state.curtainOpenPercent / 100} />
          </View>
          <Text style={styles.muted}>
            状态版本 {state.version} · 更新于 {formatTime(state.updatedAt)} · 均为模拟设备，不代表真实硬件
          </Text>
        </>
      )}
      <Button label="刷新状态" variant="secondary" onPress={onRefresh} loading={loading} disabled={disabled} />
    </Card>
  );
}

const styles = StyleSheet.create({
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: space.md },
  dim: { opacity: 0.5 },
  tile: {
    flexGrow: 1,
    flexBasis: 140,
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    padding: space.md,
    gap: space.xs,
  },
  tileName: { fontSize: font.small, color: colors.muted },
  tileValue: { fontSize: 24, fontWeight: '700', color: colors.ink },
  track: { height: 6, borderRadius: 3, backgroundColor: colors.border, overflow: 'hidden' },
  fill: { height: 6, backgroundColor: colors.blue },
  muted: { fontSize: font.caption, color: colors.muted },
  stale: { fontSize: font.small, color: colors.amber, fontWeight: '600' },
});

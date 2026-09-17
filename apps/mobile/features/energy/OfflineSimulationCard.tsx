import { StyleSheet, Text, View } from 'react-native';

import { Card } from '../../components/Card';
import { Icon, type IconName } from '../../components/Icon';
import { Pill } from '../../components/Pill';
import type { OfflineEnergySimulation } from '../../services/types';
import { colors, font, radius, space } from '../../theme/tokens';

const ASSET_ICON: Record<string, IconName> = {
  pv: 'sunny-outline',
  wind: 'flash-outline',
  base_load: 'home-outline',
  hvac: 'thermometer-outline',
  battery: 'battery-half-outline',
  grid: 'swap-horizontal-outline',
  diesel: 'shield-outline',
};

function format(value: number, unit: string, cost: boolean) {
  const text = Number.isInteger(value) ? String(value) : value.toFixed(2);
  return cost ? `$${text}` : `${text} ${unit}`;
}

export function OfflineSimulationCard({ simulation }: { simulation: OfflineEnergySimulation | null }) {
  if (!simulation) {
    return (
      <Card title="24 小时能源仿真" icon="analytics-outline" right={<Pill label="离线数据" tone="violet" />}>
        <Text style={styles.muted}>暂时无法读取离线仿真数据；当前在线规则仍可正常工作。</Text>
      </Card>
    );
  }

  const maxPv = Math.max(...simulation.profile.map((item) => item.pvKw), 1);
  const peakHours = simulation.profile.filter((item) => item.buyPriceUsdPerKwh >= 0.35).map((item) => item.hour);

  return (
    <Card title="24 小时能源仿真" icon="analytics-outline" right={<Pill label="离线 · 固定日" tone="violet" />}>
      <View testID="offline-energy-simulation" style={styles.stack}>
        <Text style={styles.intro}>
          规则策略与 MATD3 的已提供单日结果。MATD3 为单智能体离线仿真，不参与当前设备控制。
        </Text>

        <View style={styles.metrics}>
          {simulation.metrics.map((metric) => (
            <View key={metric.key} style={styles.metric}>
              <Text style={styles.metricLabel}>{metric.label}</Text>
              <View style={styles.metricRow}>
                <View style={styles.metricValue}>
                  <Text style={styles.rule}>规则</Text>
                  <Text style={styles.number}>{format(metric.rule, metric.unit, metric.key === 'daily_cost')}</Text>
                </View>
                <View style={styles.metricValue}>
                  <Text style={styles.matd3}>MATD3</Text>
                  <Text style={[styles.number, styles.modelNumber]}>{format(metric.matd3, metric.unit, metric.key === 'daily_cost')}</Text>
                </View>
              </View>
            </View>
          ))}
        </View>

        <View style={styles.profileBox}>
          <View style={styles.profileHead}>
            <Text style={styles.profileTitle}>固定日光伏输入</Text>
            <Text style={styles.profileNote}>峰电价 {peakHours[0]}:00–{peakHours[peakHours.length - 1]}:59</Text>
          </View>
          <View style={styles.bars} accessibilityLabel="24 小时光伏输入曲线">
            {simulation.profile.map((point) => (
              <View key={point.hour} style={styles.barCell}>
                <View style={[styles.bar, { height: Math.max(3, (point.pvKw / maxPv) * 38) }]} />
              </View>
            ))}
          </View>
          <View style={styles.axis}>
            <Text style={styles.axisText}>00</Text>
            <Text style={styles.axisText}>12</Text>
            <Text style={styles.axisText}>23</Text>
          </View>
        </View>

        <View style={styles.assets}>
          {simulation.assets.map((asset) => (
            <View key={asset.id} style={styles.asset}>
              <Icon name={ASSET_ICON[asset.id] ?? 'ellipse-outline'} size={17} color={colors.blue} />
              <Text style={styles.assetName}>{asset.name}</Text>
            </View>
          ))}
        </View>

        <Text style={styles.limit}>仿真范围：单一固定日 · 24 个小时步 · 美元 / 华氏度参数 · 非实时控制。</Text>
      </View>
    </Card>
  );
}

const styles = StyleSheet.create({
  stack: { gap: space.sm },
  intro: { fontSize: font.small, color: colors.muted, lineHeight: 18 },
  metrics: { flexDirection: 'row', flexWrap: 'wrap', gap: space.sm },
  metric: { flexGrow: 1, minWidth: 145, backgroundColor: colors.skyMist, borderRadius: radius.md, padding: space.sm, gap: 6 },
  metricLabel: { fontSize: font.caption, fontWeight: '700', color: colors.ink },
  metricRow: { flexDirection: 'row', gap: space.sm },
  metricValue: { flex: 1, gap: 1 },
  rule: { color: colors.muted, fontSize: 10, fontWeight: '700' },
  matd3: { color: colors.violet, fontSize: 10, fontWeight: '700' },
  number: { color: colors.ink, fontSize: font.small, fontWeight: '800' },
  modelNumber: { color: colors.violet },
  profileBox: { backgroundColor: colors.homeTint, borderRadius: radius.md, padding: space.sm, gap: 6 },
  profileHead: { flexDirection: 'row', justifyContent: 'space-between', gap: space.sm },
  profileTitle: { color: colors.ink, fontSize: font.caption, fontWeight: '700' },
  profileNote: { color: colors.muted, fontSize: 10, textAlign: 'right' },
  bars: { height: 42, flexDirection: 'row', alignItems: 'flex-end', gap: 2 },
  barCell: { flex: 1, height: 42, justifyContent: 'flex-end', backgroundColor: 'rgba(14, 165, 233, 0.08)', borderRadius: 2 },
  bar: { backgroundColor: colors.sun, borderRadius: 2, minHeight: 3 },
  axis: { flexDirection: 'row', justifyContent: 'space-between' },
  axisText: { fontSize: 10, color: colors.faint },
  assets: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  asset: { flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: colors.card, borderColor: colors.border, borderWidth: 1, paddingHorizontal: 8, paddingVertical: 5, borderRadius: radius.pill },
  assetName: { color: colors.muted, fontSize: 10, fontWeight: '600' },
  limit: { color: colors.faint, fontSize: 10, lineHeight: 15 },
  muted: { fontSize: font.small, color: colors.muted },
});

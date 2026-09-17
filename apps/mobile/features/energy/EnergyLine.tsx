import { StyleSheet, Text, View } from 'react-native';

import { Icon } from '../../components/Icon';
import type { EnergyAdvice } from '../../services/types';
import { colors, font, radius, space } from '../../theme/tokens';

const TIER = { low: '低', medium: '中', high: '高' } as const;

/** Energy advice attached to a plan. Loads are rule estimates, never measured savings. */
export function EnergyLine({ advice }: { advice: EnergyAdvice }) {
  const modeLabel = advice.mode === 'eco' ? '节能模式' : '舒适优先';
  const tariff = advice.tariff === 'peak' ? '高峰电价' : '非高峰电价';
  const headline = advice.applied
    ? `空调 ${advice.requestedAcC}°C → ${advice.recommendedAcC}°C（舒适范围 ${advice.comfortMinC}–${advice.comfortMaxC}°C）`
    : advice.recommendedAcC !== advice.requestedAcC
      ? `建议 ${advice.recommendedAcC}°C，当前保持 ${advice.requestedAcC}°C`
      : `保持 ${advice.requestedAcC}°C`;
  return (
    <View style={styles.box} testID="energy-line">
      <View style={styles.head}>
        <Icon name="leaf-outline" size={15} color={colors.green} />
        <Text style={styles.title}>
          能源智能 · {modeLabel} · {tariff}
        </Text>
      </View>
      <Text style={styles.main}>{headline}</Text>
      <Text style={styles.sub}>
        估算负荷 {advice.loadKwBefore}
        {advice.applied ? ` → ${advice.loadKwAfter}` : ''} kW（{TIER[advice.tierAfter]}档，规则估算，非实测）
      </Text>
      <Text style={styles.sub}>{advice.reason}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  box: { backgroundColor: colors.greenTint, borderRadius: radius.md, padding: space.md, gap: 3 },
  head: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  title: { fontSize: font.caption, fontWeight: '700', color: colors.green },
  main: { fontSize: font.body, fontWeight: '700', color: colors.ink },
  sub: { fontSize: font.caption, color: colors.muted, lineHeight: 17 },
});

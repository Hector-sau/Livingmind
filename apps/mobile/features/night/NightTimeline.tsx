import { StyleSheet, Text, View } from 'react-native';

import { Icon, type IconName } from '../../components/Icon';
import { PulseDot } from '../../components/motion';
import type { ScheduledStep } from '../../services/types';
import { colors, font, radius, space } from '../../theme/tokens';
import { STEP_STATUS_LABEL } from './schedule';

const PHASE_ICON: Record<ScheduledStep['phase'], IconName> = {
  sleep: 'moon-outline',
  deep: 'cloudy-night-outline',
  wake: 'sunny-outline',
};

interface Props {
  steps: ScheduledStep[];
  /** Simulated clock, shown as a header when given. */
  clock?: string | null;
  testID?: string;
}

/** Overnight schedule on a simulated clock: what runs when, and what already ran. */
export function NightTimeline({ steps, clock, testID = 'night-schedule' }: Props) {
  if (steps.length === 0) return null;
  const nextIndex = steps.findIndex((s) => s.status === 'pending');
  return (
    <View style={styles.wrap} testID={testID}>
      {clock ? (
        <View style={styles.clockRow}>
          <Icon name="time-outline" size={15} color={colors.blue} />
          <Text style={styles.clock} testID="night-clock">
            模拟时间 {clock}
          </Text>
          <Text style={styles.hint}>（演示时钟，不是真实时间）</Text>
        </View>
      ) : null}
      {steps.map((s, i) => {
        const done = s.status === 'done';
        const off = s.status === 'cancelled';
        const next = i === nextIndex;
        return (
          <View key={s.stepId} style={styles.row} testID={`night-step-${i}`}>
            <View style={styles.rail}>
              <View style={[styles.dot, done && styles.dotDone, next && styles.dotNext, off && styles.dotOff]}>
                {s.status === 'running' ? (
                  <PulseDot color={colors.sky} size={8} />
                ) : (
                  <Icon name={done ? 'checkmark' : PHASE_ICON[s.phase]} size={12} color={done ? '#FFFFFF' : off ? colors.faint : colors.blue} />
                )}
              </View>
              {i < steps.length - 1 ? <View style={[styles.line, done && styles.lineDone]} /> : null}
            </View>
            <View style={styles.body}>
              <View style={styles.head}>
                <Text style={[styles.at, off && styles.offText]}>{s.at}</Text>
                <Text style={[styles.title, off && styles.offText]} numberOfLines={2}>
                  {s.title}
                </Text>
              </View>
              <Text style={[styles.status, done && styles.statusDone, next && styles.statusNext]}>
                {next ? '下一步' : STEP_STATUS_LABEL[s.status]}
              </Text>
            </View>
          </View>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { backgroundColor: colors.skyMist, borderRadius: radius.md, padding: space.md, gap: 0 },
  clockRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: space.sm, flexWrap: 'wrap' },
  clock: { fontSize: font.body, fontWeight: '800', color: colors.ink },
  hint: { fontSize: font.caption, color: colors.muted },
  row: { flexDirection: 'row', gap: space.sm },
  rail: { width: 22, alignItems: 'center' },
  dot: {
    width: 22,
    height: 22,
    borderRadius: 11,
    borderWidth: 1.5,
    borderColor: '#BFE3F8',
    backgroundColor: colors.card,
    alignItems: 'center',
    justifyContent: 'center',
  },
  dotDone: { backgroundColor: colors.green, borderColor: colors.green },
  dotNext: { borderColor: colors.sky },
  dotOff: { borderColor: '#E2E8F0', backgroundColor: '#F8FAFC' },
  line: { flex: 1, width: 2, minHeight: 10, backgroundColor: '#D6ECF9', marginVertical: 2 },
  lineDone: { backgroundColor: '#A7E3C4' },
  body: { flex: 1, minWidth: 0, flexDirection: 'row', alignItems: 'flex-start', gap: space.sm, paddingBottom: space.sm },
  head: { flex: 1, minWidth: 0, flexDirection: 'row', gap: space.sm, alignItems: 'baseline' },
  at: { fontSize: font.small, fontWeight: '700', color: colors.ink, width: 42 },
  title: { flex: 1, fontSize: font.small, color: colors.ink, lineHeight: 19 },
  offText: { color: colors.faint, textDecorationLine: 'line-through' },
  status: { fontSize: font.caption, color: colors.muted, marginTop: 2 },
  statusDone: { color: colors.green, fontWeight: '700' },
  statusNext: { color: colors.blue, fontWeight: '700' },
});

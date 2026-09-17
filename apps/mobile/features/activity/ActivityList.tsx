import { StyleSheet, Text, View } from 'react-native';

import { Card } from '../../components/Card';
import { EmptyState } from '../../components/EmptyState';
import { Pill, type PillTone } from '../../components/Pill';
import type { ActivityRecord } from '../../services/types';
import { colors, font, space } from '../../theme/tokens';
import { ACTIVITY_KIND_LABEL, ACTIVITY_SOURCE_LABEL, formatTime } from '../../utils/format';

const TONE: Partial<Record<ActivityRecord['kind'], PillTone>> = {
  action_executed: 'green',
  action_rejected: 'red',
  plan_rejected: 'red',
  service_stopped: 'muted',
  plan_confirm_repeated: 'amber',
  plan_fallback: 'amber',
  event_received: 'violet',
  event_ignored: 'muted',
  service_adjusted: 'teal',
};

/** Raw call records. Only shown in the evidence panel. */
export function ActivityList({ items }: { items: ActivityRecord[] }) {
  return (
    <Card title="证据面板 · 原始记录" icon="document-text-outline">
      <Text style={styles.hint}>后端或本地模拟实际写入的记录，最新在上；用于评审与技术讲解。</Text>
      {items.length === 0 ? (
        <EmptyState compact icon="document-text-outline" title="暂无记录" hint="发送需求、确认计划或注入事件后，这里会出现原始记录。" />
      ) : (
        items.map((item, i) => (
          <View key={item.activityId} style={styles.row}>
            <View style={styles.rail}>
              <View style={styles.dot} />
              {i < items.length - 1 ? <View style={styles.line} /> : null}
            </View>
            <View style={styles.body}>
              <View style={styles.head}>
                <Text style={styles.time}>{formatTime(item.timestamp)}</Text>
                <Pill label={ACTIVITY_SOURCE_LABEL[item.source]} tone={TONE[item.kind] ?? 'blue'} />
                <Text style={styles.kind}>
                  {ACTIVITY_KIND_LABEL[item.kind]} · {item.kind}
                </Text>
              </View>
              <Text style={styles.message}>{item.message}</Text>
              {item.action?.reason ? <Text style={styles.reason}>原因：{item.action.reason}</Text> : null}
            </View>
          </View>
        ))
      )}
    </Card>
  );
}

const styles = StyleSheet.create({
  hint: { fontSize: font.caption, color: colors.muted },
  empty: { fontSize: font.body, color: colors.muted },
  row: { flexDirection: 'row', gap: space.md },
  rail: { width: 12, alignItems: 'center' },
  dot: { width: 10, height: 10, borderRadius: 5, backgroundColor: colors.skyLight, marginTop: 6 },
  line: { flex: 1, width: 2, backgroundColor: '#E0EEF8', marginTop: 2 },
  body: { flex: 1, gap: 2, paddingBottom: space.md },
  head: { flexDirection: 'row', alignItems: 'center', gap: space.sm, flexWrap: 'wrap' },
  time: { fontSize: font.caption, color: colors.muted, fontVariant: ['tabular-nums'] },
  kind: { fontSize: font.caption, color: colors.faint },
  message: { fontSize: font.body, color: colors.ink },
  reason: { fontSize: font.caption, color: colors.red },
});

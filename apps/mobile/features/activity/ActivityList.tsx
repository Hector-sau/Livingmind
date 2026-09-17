import { StyleSheet, Text, View } from 'react-native';

import { Card } from '../../components/Card';
import { Pill, type PillTone } from '../../components/Pill';
import type { ActivityRecord } from '../../services/types';
import { colors, font, space } from '../../theme/tokens';
import { ACTIVITY_SOURCE_LABEL, formatTime } from '../../utils/format';

const TONE: Partial<Record<ActivityRecord['kind'], PillTone>> = {
  action_executed: 'green',
  action_rejected: 'red',
  plan_rejected: 'red',
  service_stopped: 'muted',
  plan_confirm_repeated: 'amber',
};

export function ActivityList({ items }: { items: ActivityRecord[] }) {
  return (
    <Card title="服务动态">
      <Text style={styles.hint}>后端或本地模拟实际记录的事件，最新在上。</Text>
      {items.length === 0 ? (
        <Text style={styles.empty}>暂无记录。</Text>
      ) : (
        items.map((item) => (
          <View key={item.activityId} style={styles.row}>
            <Text style={styles.time}>{formatTime(item.timestamp)}</Text>
            <View style={styles.body}>
              <View style={styles.line}>
                <Pill label={ACTIVITY_SOURCE_LABEL[item.source]} tone={TONE[item.kind] ?? 'blue'} />
                <Text style={styles.kind}>{item.kind}</Text>
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
  row: { flexDirection: 'row', gap: space.md, paddingVertical: space.xs },
  time: { fontSize: font.caption, color: colors.muted, width: 62, paddingTop: 3, fontVariant: ['tabular-nums'] },
  body: { flex: 1, gap: 2 },
  line: { flexDirection: 'row', alignItems: 'center', gap: space.sm, flexWrap: 'wrap' },
  kind: { fontSize: font.caption, color: colors.muted },
  message: { fontSize: font.body, color: colors.ink },
  reason: { fontSize: font.caption, color: colors.red },
});

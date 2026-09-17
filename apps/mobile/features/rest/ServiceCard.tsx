import { StyleSheet, Text, View } from 'react-native';

import { Button } from '../../components/Button';
import { Card } from '../../components/Card';
import { EmptyState } from '../../components/EmptyState';
import { PulseDot } from '../../components/motion';
import { Pill } from '../../components/Pill';
import type { Person, Service } from '../../services/types';
import { colors, font, space } from '../../theme/tokens';
import { formatTime } from '../../utils/format';

interface Props {
  service: Service | null;
  persons: Person[];
  loading: boolean;
  disabled: boolean;
  onStop: () => void;
  /** Current AC set point; the demo event simulates the room being 3 °C warmer. */
  acTargetTempC: number | null;
  eventLoading: boolean;
  onInjectEvent: (roomTempC: number) => void;
}

export function ServiceCard({ service, persons, loading, disabled, onStop, acTargetTempC, eventLoading, onInjectEvent }: Props) {
  if (!service) {
    return (
      <Card title="休息服务" icon="moon-outline">
        <EmptyState compact icon="moon-outline" title="暂无服务" hint="在对话里确认计划后开始。" />
      </Card>
    );
  }
  const active = service.status === 'active';
  const who = persons.find((p) => p.personId === service.personId)?.name ?? service.personId;
  return (
    <Card
      title="休息服务"
      icon="moon-outline"
      right={
        active ? (
          <View style={styles.live}>
            <PulseDot color={colors.green} size={8} />
            <Text style={styles.liveText}>运行中</Text>
          </View>
        ) : (
          <Pill label="已停止" tone="muted" />
        )
      }
    >
      <Text style={styles.body}>
        {who} · {formatTime(service.startedAt).slice(0, 5)} 开始
        {service.stoppedAt ? ` · ${formatTime(service.stoppedAt).slice(0, 5)} 停止` : ''}
      </Text>
      <Text style={styles.muted}>
        自动调整 {service.adjustments} 次{service.lastAdjustedAt ? ` · 最近 ${formatTime(service.lastAdjustedAt)}` : ''}
      </Text>
      {active ? (
        <>
          <View style={styles.actions}>
            {acTargetTempC !== null ? (
              <Button
                label={`注入模拟事件：室温升到 ${acTargetTempC + 3}°C`}
                icon="thermometer-outline"
                variant="secondary"
                onPress={() => onInjectEvent(acTargetTempC + 3)}
                loading={eventLoading}
                disabled={disabled}
                testID="inject-event"
              />
            ) : null}
            <Button label="停止服务" icon="stop-circle-outline" variant="danger" onPress={onStop} loading={loading} disabled={disabled} testID="stop-service" />
          </View>
          <Text style={styles.muted}>模拟事件用于演示持续服务，没有真实传感器。停止后不再发出新的设备动作，设备保持当前状态。</Text>
        </>
      ) : (
        <Text style={styles.muted}>已停止。此前生成的计划已失效，需要重新生成。</Text>
      )}
    </Card>
  );
}

const styles = StyleSheet.create({
  body: { fontSize: font.body, color: colors.ink, fontWeight: '600' },
  muted: { fontSize: font.small, color: colors.muted },
  live: { flexDirection: 'row', alignItems: 'center', gap: 2 },
  liveText: { fontSize: font.caption, color: colors.green, fontWeight: '700' },
  actions: { flexDirection: 'row', flexWrap: 'wrap', gap: space.sm },
});

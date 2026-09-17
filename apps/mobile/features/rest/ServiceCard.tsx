import { StyleSheet, Text } from 'react-native';

import { Button } from '../../components/Button';
import { Card } from '../../components/Card';
import { Pill } from '../../components/Pill';
import type { Person, Service } from '../../services/types';
import { colors, font } from '../../theme/tokens';
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
      <Card title="休息服务">
        <Text style={styles.muted}>暂无服务。确认计划后开始。</Text>
      </Card>
    );
  }
  const active = service.status === 'active';
  const who = persons.find((p) => p.personId === service.personId)?.name ?? service.personId;
  return (
    <Card title="休息服务" right={<Pill label={active ? '运行中' : '已停止'} tone={active ? 'green' : 'muted'} />}>
      <Text style={styles.body}>
        {who} · 开始于 {formatTime(service.startedAt)}
        {service.stoppedAt ? ` · 停止于 ${formatTime(service.stoppedAt)}` : ''}
      </Text>
      <Text style={styles.muted}>
        自动调整 {service.adjustments} 次{service.lastAdjustedAt ? ` · 最近 ${formatTime(service.lastAdjustedAt)}` : ''}
      </Text>
      {active ? (
        <>
          {acTargetTempC !== null ? (
            <Button
              label={`注入模拟事件：室温升到 ${acTargetTempC + 3}°C`}
              variant="secondary"
              onPress={() => onInjectEvent(acTargetTempC + 3)}
              loading={eventLoading}
              disabled={disabled}
              testID="inject-event"
            />
          ) : null}
          <Text style={styles.muted}>模拟事件用于演示持续服务，没有真实传感器。</Text>
          <Text style={styles.muted}>停止后不再发出新的设备动作，设备保持当前状态（不会自动恢复）。</Text>
          <Button label="停止服务" variant="danger" onPress={onStop} loading={loading} disabled={disabled} testID="stop-service" />
        </>
      ) : (
        <Text style={styles.muted}>已停止。此前生成的计划已失效，需要重新生成。</Text>
      )}
    </Card>
  );
}

const styles = StyleSheet.create({
  body: { fontSize: font.body, color: colors.ink },
  muted: { fontSize: font.small, color: colors.muted },
});

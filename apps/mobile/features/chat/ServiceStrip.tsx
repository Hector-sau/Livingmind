import { StyleSheet, Text, View } from 'react-native';

import { Button } from '../../components/Button';
import { Pill } from '../../components/Pill';
import type { Service } from '../../services/types';
import { colors, font, radius, space } from '../../theme/tokens';

interface Props {
  service: Service | null;
  acTargetTempC: number | null;
  busy: boolean;
  eventLoading: boolean;
  stopLoading: boolean;
  onInjectEvent: (roomTempC: number) => void;
  onStop: () => void;
}

/** Compact status bar for the running rest service, shown above the conversation. */
export function ServiceStrip({ service, acTargetTempC, busy, eventLoading, stopLoading, onInjectEvent, onStop }: Props) {
  if (!service || service.status !== 'active') return null;
  return (
    <View style={styles.strip} testID="service-strip">
      <View style={styles.info}>
        <Pill label="休息服务运行中" tone="green" />
        <Text style={styles.text}>自动调整 {service.adjustments} 次</Text>
      </View>
      <View style={styles.actions}>
        {acTargetTempC !== null ? (
          <Button
            label={`模拟室温 ${acTargetTempC + 3}°C`}
            variant="secondary"
            onPress={() => onInjectEvent(acTargetTempC + 3)}
            loading={eventLoading}
            disabled={busy}
            testID="inject-event"
          />
        ) : null}
        <Button label="停止服务" variant="danger" onPress={onStop} loading={stopLoading} disabled={busy} testID="stop-service" />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  strip: {
    backgroundColor: colors.greenTint,
    borderRadius: radius.lg,
    padding: space.md,
    gap: space.sm,
  },
  info: { flexDirection: 'row', alignItems: 'center', gap: space.sm, flexWrap: 'wrap' },
  text: { fontSize: font.small, color: colors.ink },
  actions: { flexDirection: 'row', gap: space.sm, flexWrap: 'wrap' },
});

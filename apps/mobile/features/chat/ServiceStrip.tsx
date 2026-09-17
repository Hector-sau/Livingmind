import { LinearGradient } from 'expo-linear-gradient';
import { StyleSheet, Text, View } from 'react-native';

import { Button } from '../../components/Button';
import { FadeIn, PulseDot } from '../../components/motion';
import type { Service } from '../../services/types';
import { colors, font, gradients, radius, space } from '../../theme/tokens';

interface Props {
  service: Service | null;
  acTargetTempC: number | null;
  busy: boolean;
  eventLoading: boolean;
  stopLoading: boolean;
  onInjectEvent: (roomTempC: number) => void;
  onStop: () => void;
}

/** Status bar for the running rest service. */
export function ServiceStrip({ service, acTargetTempC, busy, eventLoading, stopLoading, onInjectEvent, onStop }: Props) {
  if (!service || service.status !== 'active') return null;
  return (
    <FadeIn>
      <LinearGradient colors={[...gradients.running]} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={styles.strip}>
        <View testID="service-strip" style={styles.inner}>
          <View style={styles.info}>
            <PulseDot color={colors.green} />
            <View>
              <Text style={styles.title}>休息服务运行中</Text>
              <Text style={styles.sub}>自动调整 {service.adjustments} 次 · 室温变化时会自动微调空调</Text>
            </View>
          </View>
          <View style={styles.actions}>
            {acTargetTempC !== null ? (
              <Button
                label={`模拟室温 ${acTargetTempC + 3}°C`}
                icon="thermometer-outline"
                variant="secondary"
                compact
                onPress={() => onInjectEvent(acTargetTempC + 3)}
                loading={eventLoading}
                disabled={busy}
                testID="inject-event"
              />
            ) : null}
            <Button label="停止服务" icon="stop-circle-outline" variant="danger" compact onPress={onStop} loading={stopLoading} disabled={busy} testID="stop-service" />
          </View>
        </View>
      </LinearGradient>
    </FadeIn>
  );
}

const styles = StyleSheet.create({
  strip: { borderRadius: radius.lg },
  inner: { padding: space.md, gap: space.sm },
  info: { flexDirection: 'row', alignItems: 'center', gap: space.sm },
  title: { fontSize: font.body, fontWeight: '700', color: colors.ink },
  sub: { fontSize: font.caption, color: colors.muted },
  actions: { flexDirection: 'row', gap: space.sm, flexWrap: 'wrap' },
});

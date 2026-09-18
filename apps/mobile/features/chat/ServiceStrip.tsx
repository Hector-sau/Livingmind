import { LinearGradient } from 'expo-linear-gradient';
import { StyleSheet, Text, View } from 'react-native';

import { Button } from '../../components/Button';
import { FadeIn, PulseDot } from '../../components/motion';
import type { Service } from '../../services/types';
import { nextPendingStep, scheduleProgress } from '../night/schedule';
import { colors, font, gradients, radius, space } from '../../theme/tokens';

interface Props {
  service: Service | null;
  acTargetTempC: number | null;
  busy: boolean;
  eventLoading: boolean;
  stopLoading: boolean;
  onInjectEvent: (roomTempC: number) => void;
  onStop: () => void;
  clockLoading: boolean;
  autoPlay: boolean;
  onAdvance: () => void;
  onSimulateSleep: () => void;
  onToggleAuto: () => void;
}

/** Status bar for the running rest service. */
export function ServiceStrip({
  service,
  acTargetTempC,
  busy,
  eventLoading,
  stopLoading,
  onInjectEvent,
  onStop,
  clockLoading,
  autoPlay,
  onAdvance,
  onSimulateSleep,
  onToggleAuto,
}: Props) {
  if (!service || service.status !== 'active') return null;
  const next = nextPendingStep(service);
  const progress = scheduleProgress(service);
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
          {progress.total > 0 ? (
            <View style={styles.night} testID="night-strip">
              <Text style={styles.clock} testID="night-clock">
                模拟时间 {service.nightClock}
              </Text>
              <Text style={styles.sub} numberOfLines={2}>
                整晚安排 {progress.done}/{progress.total}
                {next ? ` · 下一步 ${next.at} ${next.title}` : ''}
              </Text>
            </View>
          ) : null}
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
            {next ? (
              <Button
                label={service.sleepDetectedAt ? '已模拟入睡' : '模拟已入睡'}
                icon="moon-outline"
                variant="secondary"
                compact
                onPress={onSimulateSleep}
                disabled={busy || !!service.sleepDetectedAt || next.phase !== 'sleep'}
                testID="simulate-sleep"
              />
            ) : null}
            {next ? (
              <Button
                label={`快进到 ${next.at}`}
                icon="play-forward-outline"
                variant="secondary"
                compact
                onPress={onAdvance}
                loading={clockLoading && !autoPlay}
                disabled={busy || autoPlay}
                testID="clock-next"
              />
            ) : null}
            {next ? (
              <Button
                label={autoPlay ? '暂停自动播放' : '自动播放整晚'}
                icon={autoPlay ? 'pause-outline' : 'play-outline'}
                variant="ghost"
                compact
                onPress={onToggleAuto}
                disabled={busy && !autoPlay}
                testID="clock-auto"
              />
            ) : null}
            <Button label="停止服务" icon="stop-circle-outline" variant="danger" compact onPress={onStop} loading={stopLoading} disabled={stopLoading} testID="stop-service" />
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
  night: { backgroundColor: 'rgba(255,255,255,0.7)', borderRadius: radius.md, paddingHorizontal: space.md, paddingVertical: space.sm, gap: 2 },
  clock: { fontSize: font.body, fontWeight: '800', color: colors.ink },
  actions: { flexDirection: 'row', gap: space.sm, flexWrap: 'wrap' },
});

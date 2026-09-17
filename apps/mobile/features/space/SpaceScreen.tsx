import { Pressable, ScrollView, StyleSheet, Text, useWindowDimensions, View } from 'react-native';

import { Card } from '../../components/Card';
import { Icon } from '../../components/Icon';
import { Pill } from '../../components/Pill';
import { colors, font, radius, space, SPLIT_BREAKPOINT } from '../../theme/tokens';
import { ActivityList } from '../activity/ActivityList';
import { EnergyLine } from '../energy/EnergyLine';
import { DevicePanel } from '../devices/DevicePanel';
import { ServiceCard } from '../rest/ServiceCard';
import type { RestFlow } from '../rest/useRestFlow';

export function SpaceScreen({ flow, showEvidence }: { flow: RestFlow; showEvidence: boolean }) {
  const { state, actions } = flow;
  const { width } = useWindowDimensions();
  const wide = width >= SPLIT_BREAKPOINT;
  const busy = state.busy !== null;
  const data = state.data!;
  const space_ = data.spaces.find((s) => s.spaceId === data.defaultSpaceId);

  return (
    <ScrollView contentContainerStyle={styles.page}>
      <View>
        <Text style={styles.kicker}>空间</Text>
        <Text style={styles.title}>{space_?.name ?? '空间'}</Text>
      </View>
      <View style={wide ? styles.row : styles.col}>
        <View style={wide ? styles.flex : undefined}>
          <DevicePanel
            state={state.deviceState}
            stale={state.deviceStale}
            loading={state.busy === 'refresh'}
            disabled={busy}
            onRefresh={actions.refresh}
          />
        </View>
        <View style={[wide ? styles.flex : undefined, styles.col]}>
          <ServiceCard
            service={state.service}
            persons={data.persons}
            loading={state.busy === 'stop'}
            disabled={busy}
            onStop={() => void actions.stop()}
            acTargetTempC={state.deviceState?.acTargetTempC ?? null}
            eventLoading={state.busy === 'event'}
            onInjectEvent={(t) => void actions.injectEvent(t)}
          />
          <Card title="能源智能" icon="leaf-outline" right={<Pill label="规则策略" tone="green" />}>
            <View style={styles.segment}>
              {(['comfort_first', 'eco'] as const).map((m) => {
                const on = flow.space?.energyMode === m;
                return (
                  <Pressable
                    key={m}
                    onPress={() => void actions.setEnergyMode(m)}
                    disabled={busy}
                    style={[styles.segItem, on && styles.segOn]}
                    accessibilityRole="radio"
                    accessibilityState={{ selected: on }}
                    testID={`energy-mode-${m}`}
                  >
                    <Text style={[styles.segText, on && styles.segTextOn]}>{m === 'eco' ? '节能模式' : '舒适优先'}</Text>
                  </Pressable>
                );
              })}
            </View>
            <Text style={styles.muted}>
              {flow.space?.energyMode === 'eco'
                ? '节能模式：高峰电价时，在舒适范围（目标 ±1°C）内把空调设定适当提高。'
                : '舒适优先：只给出节能建议，不改变体验目标。'}
            </Text>
            {state.plan?.energy ? (
              <EnergyLine advice={state.plan.energy} />
            ) : (
              <View style={styles.energy}>
                <Icon name="leaf-outline" size={24} color={colors.faint} />
                <Text style={styles.muted}>生成休息计划后，这里会显示本次的能源建议与估算负荷档位（规则估算，非实测）。</Text>
              </View>
            )}
          </Card>
        </View>
      </View>
      {showEvidence ? (
        <View testID="evidence-panel-space">
          <ActivityList items={state.activity} />
        </View>
      ) : null}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  page: { padding: space.lg, gap: space.md, maxWidth: 1100, width: '100%', alignSelf: 'center' },
  kicker: { fontSize: font.caption, color: colors.blue, fontWeight: '700', letterSpacing: 1 },
  title: { fontSize: 24, fontWeight: '800', color: colors.ink },
  energy: { flexDirection: 'row', alignItems: 'center', gap: space.md },
  segment: { flexDirection: 'row', backgroundColor: colors.homeTint, borderRadius: radius.pill, padding: 3, alignSelf: 'flex-start' },
  segItem: { paddingHorizontal: space.lg, paddingVertical: 8, borderRadius: radius.pill },
  segOn: { backgroundColor: colors.card, boxShadow: '0px 2px 6px rgba(2, 132, 199, 0.18)' },
  segText: { fontSize: font.small, color: colors.muted, fontWeight: '700' },
  segTextOn: { color: colors.green },
  row: { flexDirection: 'row', gap: space.md, alignItems: 'flex-start' },
  col: { gap: space.md },
  flex: { flex: 1 },
  muted: { fontSize: font.small, color: colors.muted, flex: 1 },
});

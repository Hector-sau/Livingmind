import { ScrollView, StyleSheet, Text, useWindowDimensions, View } from 'react-native';

import { Card } from '../../components/Card';
import { Pill } from '../../components/Pill';
import { colors, font, space, SPLIT_BREAKPOINT } from '../../theme/tokens';
import { ActivityList } from '../activity/ActivityList';
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
      <Text style={styles.title}>{space_?.name ?? '空间'}</Text>
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
          <Card title="节能" right={<Pill label="未接入" tone="muted" />}>
            <Text style={styles.muted}>暂无数据（能源模块未接入，计划在后续步骤提供功耗档位与原因说明）。</Text>
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
  page: { padding: space.lg, gap: space.md },
  title: { fontSize: 22, fontWeight: '700', color: colors.ink },
  row: { flexDirection: 'row', gap: space.md, alignItems: 'flex-start' },
  col: { gap: space.md },
  flex: { flex: 1 },
  muted: { fontSize: font.small, color: colors.muted },
});

import { useState } from 'react';
import { ActivityIndicator, ScrollView, StyleSheet, Text, useWindowDimensions, View } from 'react-native';

import { Button } from '../../components/Button';
import { Notice } from '../../components/Notice';
import type { LivingMindApi } from '../../services';
import { colors, font, space, SPLIT_BREAKPOINT } from '../../theme/tokens';
import { ActivityList } from '../activity/ActivityList';
import { DevicePanel } from '../devices/DevicePanel';
import { PlanCard } from '../rest/PlanCard';
import { RequestCard } from '../rest/RequestCard';
import { ServiceCard } from '../rest/ServiceCard';
import { useRestFlow } from '../rest/useRestFlow';
import { PersonPicker } from './PersonPicker';

interface Props {
  api: LivingMindApi;
  backendLabel: string | null;
}

export function HomeScreen({ api, backendLabel }: Props) {
  const { width } = useWindowDimensions();
  const split = width >= SPLIT_BREAKPOINT;
  const [showActivity, setShowActivity] = useState(false);
  const { state, activeService, blockReason, actions } = useRestFlow(api);
  const busy = state.busy !== null;

  const header = (
    <View style={styles.header}>
      <View style={styles.headerText}>
        <Text style={styles.brand}>LivingMind</Text>
        <Text style={styles.subtitle}>
          Home Living · {state.data?.spaces.find((s) => s.spaceId === state.data?.defaultSpaceId)?.name ?? '—'}
        </Text>
      </View>
      <View style={[styles.mode, api.mode === 'mock' ? styles.modeMock : styles.modeHttp]}>
        <Text style={[styles.modeText, { color: api.mode === 'mock' ? colors.amber : colors.violet }]}>
          {api.mode === 'mock' ? '前端模拟模式' : `后端模式 · ${backendLabel ?? ''}`}
        </Text>
      </View>
    </View>
  );

  if (state.phase === 'loading' && !state.data) {
    return (
      <View style={styles.root}>
        {header}
        <View style={styles.center}>
          <ActivityIndicator color={colors.blue} size="large" />
          <Text style={styles.muted}>正在读取人物与设备状态…</Text>
        </View>
      </View>
    );
  }

  if (state.phase === 'error' || !state.data) {
    return (
      <View style={styles.root}>
        {header}
        <View style={[styles.center, styles.pad]}>
          <Notice
            tone="error"
            message={`加载失败：${state.error?.message ?? '未知错误'}${
              api.mode === 'http' ? '。请确认后端已启动，并且平板和电脑在同一网络。' : ''
            }`}
            actionLabel="重试"
            onAction={actions.load}
          />
        </View>
      </View>
    );
  }

  const data = state.data;

  const left = (
    <View style={styles.column}>
      <PersonPicker
        persons={data.persons}
        selectedId={state.personId}
        disabled={busy || !!activeService}
        onSelect={actions.selectPerson}
      />
      {activeService ? <Text style={styles.muted}>服务运行中，停止后才能切换人物。</Text> : null}
      <RequestCard
        value={state.utterance}
        onChange={actions.setUtterance}
        onSubmit={actions.createPlan}
        loading={state.busy === 'plan'}
        disabled={busy}
      />
      <PlanCard
        plan={state.plan}
        results={state.results}
        blockReason={blockReason}
        loading={state.busy === 'confirm'}
        disabled={busy}
        onConfirm={actions.confirm}
      />
    </View>
  );

  const right = (
    <View style={styles.column}>
      <ServiceCard
        service={state.service}
        persons={data.persons}
        loading={state.busy === 'stop'}
        disabled={busy}
        onStop={actions.stop}
      />
      <DevicePanel
        state={state.deviceState}
        stale={state.deviceStale}
        loading={state.busy === 'refresh'}
        disabled={busy}
        onRefresh={actions.refresh}
      />
      {split || showActivity ? <ActivityList items={state.activity} /> : null}
      {!split ? (
        <Button
          label={showActivity ? '收起服务动态' : `查看服务动态（${state.activity.length}）`}
          variant="secondary"
          onPress={() => setShowActivity((v) => !v)}
        />
      ) : null}
      <Button label="重置演示数据" variant="secondary" onPress={actions.resetDemo} loading={state.busy === 'reset'} disabled={busy} />
    </View>
  );

  return (
    <View style={styles.root}>
      {header}
      {state.error || state.info ? (
        <View style={styles.notices}>
          {state.error ? (
            <Notice
              tone={state.error.connectivity ? 'warning' : 'error'}
              message={state.error.message}
              actionLabel={state.error.connectivity ? '重新读取' : undefined}
              onAction={state.error.connectivity ? actions.refresh : undefined}
              onDismiss={actions.dismissError}
            />
          ) : null}
          {state.info ? <Notice tone="info" message={state.info} onDismiss={actions.dismissInfo} /> : null}
        </View>
      ) : null}
      <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
        <View style={split ? styles.split : styles.stack}>
          <View style={split ? styles.leftPane : undefined}>{left}</View>
          <View style={split ? styles.rightPane : undefined}>{right}</View>
        </View>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.surface },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    flexWrap: 'wrap',
    gap: space.sm,
    paddingHorizontal: space.xl,
    paddingVertical: space.md,
    borderTopWidth: 6,
    borderTopColor: colors.blue,
    backgroundColor: colors.card,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  headerText: { gap: 2 },
  brand: { fontSize: font.title, fontWeight: '800', color: colors.ink },
  subtitle: { fontSize: font.small, color: colors.muted },
  mode: { paddingHorizontal: space.md, paddingVertical: space.xs + 2, borderRadius: 999 },
  modeMock: { backgroundColor: colors.amberTint },
  modeHttp: { backgroundColor: '#F4F0FF' },
  modeText: { fontSize: font.small, fontWeight: '700' },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: space.md },
  pad: { padding: space.xl, alignItems: 'stretch' },
  muted: { fontSize: font.small, color: colors.muted },
  notices: { paddingHorizontal: space.lg, paddingTop: space.md, gap: space.sm },
  scroll: { padding: space.lg, gap: space.md, paddingBottom: space.xxl },
  split: { flexDirection: 'row', gap: space.lg, alignItems: 'flex-start' },
  stack: { gap: space.md },
  leftPane: { flex: 1.1 },
  rightPane: { flex: 1 },
  column: { gap: space.md },
});

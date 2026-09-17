import { useReducer, useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, useWindowDimensions, View } from 'react-native';

import { Avatar } from '../../components/Avatar';
import { Notice } from '../../components/Notice';
import type { LivingMindApi } from '../../services';
import { colors, font, radius, space, SPLIT_BREAKPOINT } from '../../theme/tokens';
import { ChatScreen } from '../chat/ChatScreen';
import { conversationReducer } from '../chat/conversation';
import { MeScreen } from '../me/MeScreen';
import { useRestFlow } from '../rest/useRestFlow';
import { ScenesScreen } from '../scenes/ScenesScreen';
import { SpaceScreen } from '../space/SpaceScreen';

type Tab = 'chat' | 'space' | 'scenes' | 'me';
const TABS: { key: Tab; label: string; icon: string }[] = [
  { key: 'chat', label: '对话', icon: '💬' },
  { key: 'space', label: '空间', icon: '🏠' },
  { key: 'scenes', label: '场景', icon: '✨' },
  { key: 'me', label: '我的', icon: '👤' },
];

export function AppShell({ api, backendLabel }: { api: LivingMindApi; backendLabel: string | null }) {
  const { width } = useWindowDimensions();
  const wide = width >= SPLIT_BREAKPOINT;
  const flow = useRestFlow(api);
  const { state, person, actions } = flow;
  const [tab, setTab] = useState<Tab>('chat');
  const [showEvidence, setShowEvidence] = useState(false);
  const [conversations, dispatch] = useReducer(conversationReducer, {});

  const header = (
    <View style={styles.header}>
      <View style={styles.brandRow}>
        <View style={styles.logoMark} />
        <View>
          <Text style={styles.brand}>LivingMind</Text>
          <Text style={styles.subtitle}>
            Home Living · {state.data?.spaces.find((s) => s.spaceId === state.data?.defaultSpaceId)?.name ?? '—'}
          </Text>
        </View>
      </View>
      <View style={styles.headerRight}>
        <View style={[styles.mode, api.mode === 'mock' ? styles.modeMock : styles.modeHttp]}>
          <Text style={[styles.modeText, { color: api.mode === 'mock' ? colors.amber : colors.violet }]}>
            {api.mode === 'mock' ? '前端模拟模式' : `后端 · ${backendLabel ?? ''}`}
          </Text>
        </View>
        {person ? (
          <Pressable style={styles.who} onPress={() => setTab('me')} accessibilityRole="button" testID="current-person">
            <Avatar name={person.name} color={person.avatarColor} size={32} />
            <Text style={styles.whoName}>{person.name}</Text>
          </Pressable>
        ) : null}
      </View>
    </View>
  );

  if (state.phase === 'loading' && !state.data) {
    return (
      <View style={styles.root}>
        {header}
        <View style={styles.center}>
          <ActivityIndicator color={colors.blue} size="large" />
          <Text style={styles.muted}>正在连接…</Text>
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

  const nav = (
    <View style={wide ? styles.rail : styles.tabbar}>
      {TABS.map((t) => {
        const on = t.key === tab;
        return (
          <Pressable
            key={t.key}
            onPress={() => setTab(t.key)}
            style={[wide ? styles.railItem : styles.tabItem, on && styles.navOn]}
            accessibilityRole="tab"
            accessibilityState={{ selected: on }}
            testID={`tab-${t.key}`}
          >
            <Text style={styles.navIcon}>{t.icon}</Text>
            <Text style={[styles.navLabel, on && styles.navLabelOn]}>{t.label}</Text>
          </Pressable>
        );
      })}
    </View>
  );

  const screen =
    tab === 'chat' ? (
      <ChatScreen api={api} flow={flow} messages={conversations[state.personId ?? 'none'] ?? []} dispatch={dispatch} />
    ) : tab === 'space' ? (
      <SpaceScreen flow={flow} showEvidence={showEvidence} />
    ) : tab === 'scenes' ? (
      <ScenesScreen flow={flow} />
    ) : (
      <MeScreen api={api} flow={flow} showEvidence={showEvidence} onToggleEvidence={setShowEvidence} />
    );

  const notices =
    state.error || state.info ? (
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
    ) : null;

  return (
    <View style={styles.root}>
      {header}
      {notices}
      {wide ? (
        <View style={styles.body}>
          {nav}
          <View style={styles.content}>{screen}</View>
        </View>
      ) : (
        <>
          <View style={styles.content}>{screen}</View>
          {nav}
        </>
      )}
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
    backgroundColor: colors.card,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  brandRow: { flexDirection: 'row', alignItems: 'center', gap: space.md },
  logoMark: { width: 28, height: 28, borderRadius: 8, backgroundColor: colors.blue },
  brand: { fontSize: font.title - 4, fontWeight: '800', color: colors.ink },
  subtitle: { fontSize: font.caption, color: colors.muted },
  headerRight: { flexDirection: 'row', alignItems: 'center', gap: space.md },
  mode: { paddingHorizontal: space.md, paddingVertical: space.xs + 2, borderRadius: radius.pill },
  modeMock: { backgroundColor: colors.amberTint },
  modeHttp: { backgroundColor: '#F4F0FF' },
  modeText: { fontSize: font.caption, fontWeight: '700' },
  who: { flexDirection: 'row', alignItems: 'center', gap: space.sm },
  whoName: { fontSize: font.body, fontWeight: '600', color: colors.ink },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: space.md },
  pad: { padding: space.xl, alignItems: 'stretch' },
  muted: { fontSize: font.small, color: colors.muted },
  notices: { paddingHorizontal: space.lg, paddingTop: space.md, gap: space.sm },
  body: { flex: 1, flexDirection: 'row' },
  content: { flex: 1 },
  rail: {
    width: 88,
    paddingVertical: space.lg,
    gap: space.sm,
    alignItems: 'center',
    backgroundColor: colors.card,
    borderRightWidth: 1,
    borderRightColor: colors.border,
  },
  railItem: { width: 68, paddingVertical: space.sm, borderRadius: radius.md, alignItems: 'center', gap: 2 },
  tabbar: {
    flexDirection: 'row',
    backgroundColor: colors.card,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    paddingBottom: space.sm,
  },
  tabItem: { flex: 1, paddingVertical: space.sm, alignItems: 'center', gap: 2 },
  navOn: { backgroundColor: colors.homeTint },
  navIcon: { fontSize: 20 },
  navLabel: { fontSize: font.caption, color: colors.muted, fontWeight: '600' },
  navLabelOn: { color: colors.blue },
});

import { LinearGradient } from 'expo-linear-gradient';
import { useEffect, useReducer, useState } from 'react';
import { Image, Pressable, StyleSheet, Text, useWindowDimensions, View } from 'react-native';

import { Avatar } from '../../components/Avatar';
import { Icon, type IconName } from '../../components/Icon';
import { Skeleton } from '../../components/motion';
import { Notice } from '../../components/Notice';
import type { LivingMindApi } from '../../services';
import { colors, font, gradients, radius, space, SPLIT_BREAKPOINT } from '../../theme/tokens';
import { ChatScreen } from '../chat/ChatScreen';
import { conversationReducer } from '../chat/conversation';
import { MeScreen } from '../me/MeScreen';
import { useRestFlow } from '../rest/useRestFlow';
import { ScenesScreen } from '../scenes/ScenesScreen';
import { SpaceScreen } from '../space/SpaceScreen';
import { autoDismissDelay } from './notices';

const LOGO = require('../../assets/logo-horizontal.png');

type Tab = 'chat' | 'space' | 'scenes' | 'me';
const TABS: { key: Tab; label: string; icon: IconName; iconOn: IconName }[] = [
  { key: 'chat', label: '对话', icon: 'chatbubbles-outline', iconOn: 'chatbubbles' },
  { key: 'space', label: '空间', icon: 'home-outline', iconOn: 'home' },
  { key: 'scenes', label: '场景', icon: 'sparkles-outline', iconOn: 'sparkles' },
  { key: 'me', label: '我的', icon: 'person-circle-outline', iconOn: 'person-circle' },
];

export function AppShell({ api, backendLabel }: { api: LivingMindApi; backendLabel: string | null }) {
  const { width } = useWindowDimensions();
  const wide = width >= SPLIT_BREAKPOINT;
  const flow = useRestFlow(api);
  const { state, person, actions } = flow;
  const [tab, setTab] = useState<Tab>('chat');
  const [showEvidence, setShowEvidence] = useState(false);
  const [conversations, dispatch] = useReducer(conversationReducer, {});
  const spaceName = state.data?.spaces.find((s) => s.spaceId === state.data?.defaultSpaceId)?.name;

  // Info notices fade on their own; warnings and errors stay until dismissed.
  const dismissInfo = actions.dismissInfo;
  useEffect(() => {
    const delay = autoDismissDelay(state.info ? 'info' : null);
    if (delay === null) return;
    const timer = setTimeout(dismissInfo, delay);
    return () => clearTimeout(timer);
  }, [state.info, dismissInfo]);

  /** One tap before presenting: fresh data, 林悦, comfort first, empty chats, chat tab. */
  const prepareDemo = async () => {
    const res = await actions.resetDemo(false, '演示已准备好：林悦 · 舒适优先 · 设备回到初始状态');
    if (res.ok) {
      dispatch({ type: 'clearAll' });
      setShowEvidence(false);
      setTab('chat');
    }
  };

  const header = (
    <View style={styles.header}>
      <View style={styles.brandRow}>
        <Image source={LOGO} style={styles.logo} resizeMode="contain" accessibilityLabel="LivingMind" />
        {wide && spaceName ? (
          <View style={styles.spaceChip}>
            <Icon name="location-outline" size={13} color={colors.muted} />
            <Text style={styles.spaceText}>Home Living · {spaceName}</Text>
          </View>
        ) : null}
      </View>
      <View style={styles.headerRight}>
        <View style={styles.mode} accessibilityLabel={api.mode === 'mock' ? '前端模拟模式' : '后端模式'}>
          <View style={[styles.modeDot, { backgroundColor: api.mode === 'mock' ? colors.sun : colors.green }]} />
          <Text style={styles.modeText}>
            {api.mode === 'mock' ? '前端模拟模式' : wide ? `后端 · ${backendLabel ?? ''}` : '后端'}
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

  const frame = (children: React.ReactNode) => (
    <LinearGradient colors={[...gradients.page]} style={styles.root}>
      {header}
      {children}
    </LinearGradient>
  );

  if (state.phase === 'loading' && !state.data) {
    return frame(
      <View style={styles.loading}>
        <Skeleton width="60%" height={20} />
        <Skeleton width="85%" height={120} radius={20} />
        <Skeleton width="70%" height={90} radius={20} />
        <Text style={styles.muted}>正在连接…</Text>
      </View>,
    );
  }
  if (state.phase === 'error' || !state.data) {
    return frame(
      <View style={styles.loading}>
        <Notice
          tone="error"
          message={`加载失败：${state.error?.message ?? '未知错误'}${
            api.mode === 'http' ? '。请确认后端已启动，并且平板和电脑在同一网络。' : ''
          }`}
          actionLabel="重试"
          onAction={actions.load}
        />
      </View>,
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
            style={wide ? styles.railItem : styles.tabItem}
            accessibilityRole="tab"
            accessibilityState={{ selected: on }}
            testID={`tab-${t.key}`}
          >
            <View style={[styles.navIcon, on && styles.navIconOn]}>
              <Icon name={on ? t.iconOn : t.icon} size={22} color={on ? colors.blue : colors.faint} />
            </View>
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
      <SpaceScreen api={api} flow={flow} showEvidence={showEvidence} />
    ) : tab === 'scenes' ? (
      <ScenesScreen flow={flow} onOpenChat={() => setTab('chat')} />
    ) : (
      <MeScreen
        api={api}
        flow={flow}
        showEvidence={showEvidence}
        onToggleEvidence={setShowEvidence}
        onPrepareDemo={prepareDemo}
      />
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

  return frame(
    wide ? (
      <View style={styles.body}>
        {nav}
        <View style={styles.content}>
          {notices}
          {screen}
        </View>
      </View>
    ) : (
      <>
        {notices}
        <View style={styles.content}>{screen}</View>
        {nav}
      </>
    ),
  );
}

const styles = StyleSheet.create({
  root: { flex: 1 },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: space.sm,
    paddingHorizontal: space.lg,
    paddingVertical: space.sm + 2,
    backgroundColor: 'rgba(255,255,255,0.85)',
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  brandRow: { flexDirection: 'row', alignItems: 'center', gap: space.md, flexShrink: 1 },
  logo: { width: 120, height: 35 },
  spaceChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: space.sm + 2,
    paddingVertical: 4,
    borderRadius: radius.pill,
    backgroundColor: colors.skyMist,
  },
  spaceText: { fontSize: font.caption, color: colors.muted, fontWeight: '600' },
  headerRight: { flexDirection: 'row', alignItems: 'center', gap: space.sm, flexShrink: 0 },
  mode: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: space.sm + 2,
    paddingVertical: 5,
    borderRadius: radius.pill,
    backgroundColor: colors.card,
    borderWidth: 1,
    borderColor: colors.border,
  },
  modeDot: { width: 8, height: 8, borderRadius: 4 },
  modeText: { fontSize: font.caption, fontWeight: '700', color: colors.muted },
  who: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  whoName: { fontSize: font.small, fontWeight: '700', color: colors.ink },
  loading: { flex: 1, padding: space.xl, gap: space.lg, alignItems: 'center', justifyContent: 'center' },
  muted: { fontSize: font.small, color: colors.muted },
  notices: { paddingHorizontal: space.lg, paddingTop: space.md, gap: space.sm },
  body: { flex: 1, flexDirection: 'row' },
  content: { flex: 1 },
  rail: {
    width: 92,
    paddingVertical: space.lg,
    gap: space.md,
    alignItems: 'center',
    backgroundColor: 'rgba(255,255,255,0.7)',
    borderRightWidth: 1,
    borderRightColor: colors.border,
  },
  railItem: { width: 76, alignItems: 'center', gap: 4, paddingVertical: 4 },
  tabbar: {
    flexDirection: 'row',
    backgroundColor: 'rgba(255,255,255,0.95)',
    borderTopWidth: 1,
    borderTopColor: colors.border,
    paddingTop: 6,
    paddingBottom: space.sm,
  },
  tabItem: { flex: 1, alignItems: 'center', gap: 2 },
  navIcon: { width: 48, height: 32, borderRadius: 16, alignItems: 'center', justifyContent: 'center' },
  navIconOn: { backgroundColor: colors.homeTint },
  navLabel: { fontSize: font.caption, color: colors.faint, fontWeight: '600' },
  navLabelOn: { color: colors.blue },
});

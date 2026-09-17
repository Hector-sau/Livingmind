import { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import { Button } from '../../components/Button';
import { EmptyState } from '../../components/EmptyState';
import { Icon, type IconName } from '../../components/Icon';
import { FadeIn } from '../../components/motion';
import { Pill } from '../../components/Pill';
import type { Scene } from '../../services/types';
import { colors, font, radius, shadow, space } from '../../theme/tokens';
import { TraceView } from '../agents/TraceView';
import type { RestFlow } from '../rest/useRestFlow';
import { sceneTimeline } from './timeline';

const SCENE_ICON: Record<string, { icon: IconName; color: string; tint: string }> = {
  'scene-rest': { icon: 'bed-outline', color: colors.blue, tint: colors.homeTint },
  'scene-room-temp': { icon: 'thermometer-outline', color: '#0E8C8D', tint: colors.tealTint },
  'scene-wake': { icon: 'sunny-outline', color: colors.amber, tint: colors.amberTint },
};

/** Wording mirrors AGENT-HANDOFF 0.4: only Experience may call a model; the rest are rules. */
const ROLES: { icon: IconName; color: string; name: string; tag: string; text: string }[] = [
  { icon: 'git-network-outline', color: colors.blue, name: '主 Agent', tag: '规则路由与编排', text: '判断意图，按顺序调度记忆、体验、能源和执行，并记录每一步。' },
  { icon: 'sparkles-outline', color: '#0E8C8D', name: 'Experience Agent', tag: '可调用大模型', text: '结合个人偏好生成灯光、空调、窗帘目标；超出范围或失败时用规则降级。' },
  { icon: 'hardware-chip-outline', color: colors.sky, name: 'Space Execution Agent', tag: '规则', text: '把目标翻译成设备动作，交给执行器；不直接写设备。' },
  { icon: 'shield-checkmark-outline', color: colors.amber, name: '记忆 · 能源规则 · Harness', tag: '支撑模块', text: '只读本人偏好；峰时电价按规则给建议；执行前做安全与并发检查。' },
];

export function ScenesScreen({ flow, onOpenChat }: { flow: RestFlow; onOpenChat: () => void }) {
  const { state } = flow;
  const [open, setOpen] = useState<string | null>(null);
  const trace = state.plan?.trace ?? [];

  const card = (scene: Scene, index: number) => {
    const expanded = open === scene.sceneId;
    const implemented = scene.status === 'implemented';
    const timeline = expanded && implemented ? sceneTimeline(scene.sceneId, state.activity) : [];
    const look = SCENE_ICON[scene.sceneId] ?? SCENE_ICON['scene-rest'];
    return (
      <FadeIn key={scene.sceneId} delay={index * 60}>
        <Pressable
          style={[styles.card, expanded && styles.cardOpen]}
          onPress={() => setOpen(expanded ? null : scene.sceneId)}
          accessibilityRole="button"
          testID={`scene-card-${scene.sceneId}`}
        >
          <View style={styles.head}>
            <View style={[styles.iconCircle, { backgroundColor: look.tint }]}>
              <Icon name={look.icon} size={22} color={look.color} />
            </View>
            <View style={styles.headText}>
              <Text style={styles.title}>{scene.title}</Text>
              <Text style={styles.meta}>触发：{scene.trigger}</Text>
            </View>
            <Pill label={implemented ? '已实现' : '规划中'} tone={implemented ? 'green' : 'muted'} testID={`scene-status-${scene.sceneId}`} />
          </View>
          <Text style={styles.desc}>{scene.description}</Text>
          <Text style={styles.meta}>{scene.verification}</Text>
          {expanded ? (
            <View style={styles.timeline}>
              {!implemented ? (
                <Text style={styles.muted}>尚未实现，暂无执行记录。</Text>
              ) : timeline.length === 0 ? (
                <EmptyState compact icon="time-outline" title="还没有执行记录" hint="本次运行还没有这个场景的执行记录。" />
              ) : (
                timeline.map((e, i) => (
                  <View key={e.id} style={styles.entry}>
                    <View style={styles.rail}>
                      <View style={styles.dot} />
                      {i < timeline.length - 1 ? <View style={styles.line} /> : null}
                    </View>
                    <Text style={styles.time}>{e.time}</Text>
                    <Text style={styles.entryText}>{e.text}</Text>
                  </View>
                ))
              )}
            </View>
          ) : (
            <View style={styles.more}>
              <Text style={styles.moreText}>查看执行记录</Text>
              <Icon name="chevron-down" size={14} color={colors.blue} />
            </View>
          )}
        </Pressable>
      </FadeIn>
    );
  };

  return (
    <ScrollView contentContainerStyle={styles.page}>
      <View>
        <Text style={styles.kicker}>场景</Text>
        <Text style={styles.pageTitle}>主动服务场景</Text>
        <Text style={styles.muted}>标签按真实实现情况标注；点开查看本次运行的执行记录。</Text>
      </View>
      <FadeIn>
        <View style={styles.explain} testID="agent-explainer">
          <View style={styles.head}>
            <View style={[styles.iconCircle, { backgroundColor: colors.homeTint }]}>
              <Icon name="git-network-outline" size={22} color={colors.blue} />
            </View>
            <View style={styles.headText}>
              <Text style={styles.title}>1+2 Agent 如何协作</Text>
              <Text style={styles.meta}>1 个主 Agent 编排，2 个专职 Agent 分工；设备只经执行器写入。</Text>
            </View>
          </View>
          {ROLES.map((r) => (
            <View key={r.name} style={styles.role}>
              <Icon name={r.icon} size={18} color={r.color} />
              <View style={styles.headText}>
                <View style={styles.roleHead}>
                  <Text style={styles.roleName}>{r.name}</Text>
                  <Text style={styles.roleTag}>{r.tag}</Text>
                </View>
                <Text style={styles.roleText}>{r.text}</Text>
              </View>
            </View>
          ))}
          {trace.length > 0 ? (
            <View style={styles.latest} testID="explainer-trace">
              <Text style={styles.meta}>最近一次计划的真实协作过程：</Text>
              <TraceView trace={trace} />
            </View>
          ) : (
            <View style={styles.latest}>
              <Text style={styles.meta}>还没有计划。去对话里说一句“我想休息一下”，这里会显示真实的协作过程。</Text>
              <View style={styles.cta}>
                <Button label="去对话" icon="chatbubble-ellipses-outline" variant="secondary" compact onPress={onOpenChat} testID="explainer-open-chat" />
              </View>
            </View>
          )}
        </View>
      </FadeIn>
      {state.scenes.map(card)}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  page: { padding: space.lg, gap: space.md, maxWidth: 760, width: '100%', alignSelf: 'center' },
  kicker: { fontSize: font.caption, color: colors.blue, fontWeight: '700', letterSpacing: 1 },
  pageTitle: { fontSize: 24, fontWeight: '800', color: colors.ink },
  card: {
    backgroundColor: colors.card,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: '#EDF4FA',
    padding: space.lg + 2,
    gap: space.sm,
    ...shadow.card,
  },
  explain: {
    backgroundColor: colors.card,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: '#CFE8FA',
    padding: space.lg + 2,
    gap: space.md,
    ...shadow.card,
  },
  role: { flexDirection: 'row', alignItems: 'flex-start', gap: space.md, paddingLeft: space.xs },
  roleHead: { flexDirection: 'row', alignItems: 'center', gap: space.sm, flexWrap: 'wrap' },
  roleName: { fontSize: font.body, fontWeight: '700', color: colors.ink },
  roleTag: { fontSize: font.caption, color: colors.blue, backgroundColor: colors.skyMist, paddingHorizontal: 8, paddingVertical: 2, borderRadius: 999, overflow: 'hidden' },
  roleText: { fontSize: font.small, color: colors.muted, lineHeight: 19 },
  latest: { borderTopWidth: 1, borderTopColor: '#EDF4FA', paddingTop: space.md, gap: space.sm },
  cta: { alignSelf: 'flex-start' },
  cardOpen: { borderColor: '#9ED8F7', ...shadow.raised },
  head: { flexDirection: 'row', alignItems: 'center', gap: space.md },
  headText: { flex: 1, gap: 2 },
  iconCircle: { width: 44, height: 44, borderRadius: 22, alignItems: 'center', justifyContent: 'center' },
  title: { fontSize: font.section, fontWeight: '700', color: colors.ink },
  desc: { fontSize: font.body, color: colors.ink, lineHeight: 22 },
  meta: { fontSize: font.caption, color: colors.muted },
  muted: { fontSize: font.small, color: colors.muted },
  more: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  moreText: { fontSize: font.small, color: colors.blue, fontWeight: '600' },
  timeline: { marginTop: space.sm, backgroundColor: colors.skyMist, borderRadius: radius.md, padding: space.md },
  entry: { flexDirection: 'row', alignItems: 'flex-start', gap: space.sm, minHeight: 30 },
  rail: { width: 10, alignItems: 'center', alignSelf: 'stretch' },
  dot: { width: 8, height: 8, borderRadius: 4, backgroundColor: colors.sky, marginTop: 6 },
  line: { flex: 1, width: 2, backgroundColor: '#CFE8FA' },
  time: { fontSize: font.caption, color: colors.muted, width: 40, marginTop: 2 },
  entryText: { flex: 1, fontSize: font.body, color: colors.ink },
});

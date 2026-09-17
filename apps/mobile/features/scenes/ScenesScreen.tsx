import { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import { Icon, type IconName } from '../../components/Icon';
import { FadeIn } from '../../components/motion';
import { Pill } from '../../components/Pill';
import type { Scene } from '../../services/types';
import { colors, font, radius, shadow, space } from '../../theme/tokens';
import type { RestFlow } from '../rest/useRestFlow';
import { sceneTimeline } from './timeline';

const SCENE_ICON: Record<string, { icon: IconName; color: string; tint: string }> = {
  'scene-rest': { icon: 'bed-outline', color: colors.blue, tint: colors.homeTint },
  'scene-room-temp': { icon: 'thermometer-outline', color: '#0E8C8D', tint: colors.tealTint },
  'scene-wake': { icon: 'sunny-outline', color: colors.amber, tint: colors.amberTint },
};

export function ScenesScreen({ flow }: { flow: RestFlow }) {
  const { state } = flow;
  const [open, setOpen] = useState<string | null>(null);

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
                <Text style={styles.muted}>本次运行还没有这个场景的执行记录。</Text>
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

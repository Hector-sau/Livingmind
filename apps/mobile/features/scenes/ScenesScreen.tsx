import { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import { Pill } from '../../components/Pill';
import type { Scene } from '../../services/types';
import { colors, font, radius, space } from '../../theme/tokens';
import type { RestFlow } from '../rest/useRestFlow';
import { sceneTimeline } from './timeline';

export function ScenesScreen({ flow }: { flow: RestFlow }) {
  const { state } = flow;
  const [open, setOpen] = useState<string | null>(null);

  const card = (scene: Scene) => {
    const expanded = open === scene.sceneId;
    const implemented = scene.status === 'implemented';
    const timeline = expanded && implemented ? sceneTimeline(scene.sceneId, state.activity) : [];
    return (
      <Pressable
        key={scene.sceneId}
        style={[styles.card, expanded && styles.cardOpen]}
        onPress={() => setOpen(expanded ? null : scene.sceneId)}
        accessibilityRole="button"
        testID={`scene-card-${scene.sceneId}`}
      >
        <View style={styles.head}>
          <Text style={styles.title}>{scene.title}</Text>
          <Pill label={implemented ? '已实现' : '规划中'} tone={implemented ? 'green' : 'muted'} />
        </View>
        <Text style={styles.desc}>{scene.description}</Text>
        <Text style={styles.meta}>
          触发：{scene.trigger} · {scene.verification}
        </Text>
        {expanded ? (
          <View style={styles.timeline}>
            {!implemented ? (
              <Text style={styles.muted}>尚未实现，暂无执行记录。</Text>
            ) : timeline.length === 0 ? (
              <Text style={styles.muted}>本次运行还没有这个场景的执行记录。</Text>
            ) : (
              timeline.map((e) => (
                <View key={e.id} style={styles.entry}>
                  <View style={styles.dot} />
                  <Text style={styles.time}>{e.time}</Text>
                  <Text style={styles.entryText}>{e.text}</Text>
                </View>
              ))
            )}
          </View>
        ) : null}
      </Pressable>
    );
  };

  return (
    <ScrollView contentContainerStyle={styles.page}>
      <Text style={styles.pageTitle}>主动服务场景</Text>
      <Text style={styles.muted}>标签按真实实现情况标注；点开查看本次运行的执行记录。</Text>
      {state.scenes.map(card)}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  page: { padding: space.lg, gap: space.md, maxWidth: 760, width: '100%', alignSelf: 'center' },
  pageTitle: { fontSize: 22, fontWeight: '700', color: colors.ink },
  card: {
    backgroundColor: colors.card,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.border,
    padding: space.lg,
    gap: space.sm,
  },
  cardOpen: { borderColor: colors.blue },
  head: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: space.sm },
  title: { fontSize: font.section, fontWeight: '700', color: colors.ink },
  desc: { fontSize: font.body, color: colors.ink },
  meta: { fontSize: font.caption, color: colors.muted },
  muted: { fontSize: font.small, color: colors.muted },
  timeline: { gap: space.sm, marginTop: space.sm },
  entry: { flexDirection: 'row', alignItems: 'center', gap: space.sm },
  dot: { width: 8, height: 8, borderRadius: 4, backgroundColor: colors.blue },
  time: { fontSize: font.caption, color: colors.muted, width: 44 },
  entryText: { flex: 1, fontSize: font.body, color: colors.ink },
});

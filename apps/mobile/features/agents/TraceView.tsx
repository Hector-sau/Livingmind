import { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { Icon, type IconName } from '../../components/Icon';
import { FadeIn } from '../../components/motion';
import { Pill, type PillTone } from '../../components/Pill';
import type { AgentStep } from '../../services/types';
import { colors, font, radius, space } from '../../theme/tokens';

const AGENT: Record<AgentStep['agent'], { name: string; icon: IconName; color: string }> = {
  orchestrator: { name: '主 Agent', icon: 'git-network-outline', color: colors.blue },
  memory: { name: '人物记忆', icon: 'person-circle-outline', color: '#7C5CE5' },
  experience: { name: 'Experience Agent', icon: 'sparkles-outline', color: '#0E8C8D' },
  energy: { name: '能源智能', icon: 'leaf-outline', color: colors.green },
  space_execution: { name: 'Space Execution Agent', icon: 'hardware-chip-outline', color: colors.sky },
  harness: { name: 'Harness', icon: 'shield-checkmark-outline', color: colors.amber },
};

const SOURCE: Record<AgentStep['source'], { label: string; tone: PillTone }> = {
  rule: { label: '规则', tone: 'violet' },
  model: { label: '模型', tone: 'teal' },
  rule_fallback: { label: '规则降级', tone: 'amber' },
  frontend_mock: { label: '前端模拟', tone: 'amber' },
};

/** The 1 + 2 agent collaboration for one plan, collapsed by default. */
export function TraceView({ trace }: { trace: AgentStep[] }) {
  const [open, setOpen] = useState(false);
  if (trace.length === 0) return null;
  return (
    <View style={styles.wrap}>
      <Pressable style={styles.toggle} onPress={() => setOpen((v) => !v)} accessibilityRole="button" testID="trace-toggle">
        <Icon name="git-network-outline" size={15} color={colors.blue} />
        <Text style={styles.toggleText}>{open ? '收起协作过程' : `查看协作过程（${trace.length} 步）`}</Text>
        <Icon name={open ? 'chevron-up' : 'chevron-down'} size={14} color={colors.blue} />
      </Pressable>
      {open ? (
        <FadeIn>
          <View style={styles.panel} testID="trace-panel">
            {trace.map((s, i) => {
              const a = AGENT[s.agent];
              const src = SOURCE[s.source];
              return (
                <View key={`${s.agent}-${i}`} style={styles.row}>
                  <View style={styles.rail}>
                    <View style={[styles.icon, { borderColor: a.color }]}>
                      <Icon name={a.icon} size={14} color={a.color} />
                    </View>
                    {i < trace.length - 1 ? <View style={styles.line} /> : null}
                  </View>
                  <View style={styles.body}>
                    <View style={styles.head}>
                      <Text style={styles.agent}>{a.name}</Text>
                      <Text style={styles.title}>{s.title}</Text>
                      <Pill label={src.label} tone={s.ok ? src.tone : 'amber'} />
                      <Text style={styles.ms}>{s.latencyMs} ms</Text>
                    </View>
                    <Text style={styles.detail}>{s.detail}</Text>
                  </View>
                </View>
              );
            })}
          </View>
        </FadeIn>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { gap: space.sm },
  toggle: { flexDirection: 'row', alignItems: 'center', gap: 6, alignSelf: 'flex-start', paddingVertical: 4 },
  toggleText: { fontSize: font.small, color: colors.blue, fontWeight: '700' },
  panel: { backgroundColor: colors.skyMist, borderRadius: radius.md, padding: space.md },
  row: { flexDirection: 'row', gap: space.sm },
  rail: { width: 26, alignItems: 'center' },
  icon: {
    width: 26,
    height: 26,
    borderRadius: 13,
    borderWidth: 1.5,
    backgroundColor: colors.card,
    alignItems: 'center',
    justifyContent: 'center',
  },
  line: { flex: 1, width: 2, backgroundColor: '#CFE8FA', marginVertical: 2 },
  body: { flex: 1, gap: 2, paddingBottom: space.md },
  head: { flexDirection: 'row', alignItems: 'center', gap: 6, flexWrap: 'wrap' },
  agent: { fontSize: font.small, fontWeight: '800', color: colors.ink },
  title: { fontSize: font.small, color: colors.muted },
  ms: { fontSize: font.caption, color: colors.faint },
  detail: { fontSize: font.small, color: colors.ink, lineHeight: 19 },
});

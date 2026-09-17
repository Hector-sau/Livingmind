import { Pressable, StyleSheet, Text, View } from 'react-native';

import type { PlannerInfo, PlannerMode } from '../../services/types';
import { colors, font, radius, space } from '../../theme/tokens';

interface Props {
  value: PlannerMode;
  planner: PlannerInfo;
  apiMode: 'mock' | 'http';
  disabled?: boolean;
  onChange: (mode: PlannerMode) => void;
}

/** Rule vs model planning. Model mode always exists so the fallback path can be demonstrated honestly. */
export function ModeToggle({ value, planner, apiMode, disabled, onChange }: Props) {
  const options: { key: PlannerMode; label: string }[] = [
    { key: 'rule', label: '规则' },
    { key: 'model', label: '模型' },
  ];
  const hint =
    apiMode === 'mock'
      ? value === 'rule'
        ? '规则模式：前端本地规则生成计划（前端模拟）。'
        : '模型模式：前端模拟模式没有模型，将改用本地规则并标注。'
      : value === 'rule'
      ? '规则模式：后端固定规则生成计划，不调用模型。'
      : planner.modelConfigured
        ? `模型模式：Experience Agent 调用 ${planner.provider}/${planner.model}；失败时降级为规则并标注。`
        : '模型模式：后端未配置模型，将降级为规则计划并标注原因。';
  return (
    <View style={styles.wrap}>
      <View style={styles.row}>
        <Text style={styles.label}>计划来源</Text>
        <View style={styles.segment} accessibilityRole="radiogroup">
          {options.map((o) => {
            const on = o.key === value;
            return (
              <Pressable
                key={o.key}
                accessibilityRole="radio"
                accessibilityState={{ selected: on, disabled: !!disabled }}
                disabled={disabled}
                onPress={() => onChange(o.key)}
                style={[styles.option, on && styles.optionOn, disabled && styles.disabled]}
                testID={`mode-${o.key}`}
              >
                <Text style={[styles.optionText, on && styles.optionTextOn]}>{o.label}</Text>
              </Pressable>
            );
          })}
        </View>
      </View>
      <Text style={styles.hint}>{hint}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { gap: space.xs },
  row: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: space.sm },
  label: { fontSize: font.small, color: colors.muted },
  segment: { flexDirection: 'row', backgroundColor: colors.surface, borderRadius: radius.pill, padding: 3 },
  option: { paddingHorizontal: space.lg, paddingVertical: space.xs + 2, borderRadius: radius.pill, minHeight: 32, justifyContent: 'center' },
  optionOn: { backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border },
  optionText: { fontSize: font.small, color: colors.muted, fontWeight: '600' },
  optionTextOn: { color: colors.ink },
  disabled: { opacity: 0.5 },
  hint: { fontSize: font.caption, color: colors.muted },
});

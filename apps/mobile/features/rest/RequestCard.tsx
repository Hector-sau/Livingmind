import { StyleSheet, Text, TextInput } from 'react-native';

import { Button } from '../../components/Button';
import { Card } from '../../components/Card';
import type { PlannerInfo, PlannerMode } from '../../services/types';
import { colors, font, radius, space } from '../../theme/tokens';
import { ModeToggle } from './ModeToggle';

interface Props {
  value: string;
  onChange: (v: string) => void;
  onSubmit: () => void;
  loading: boolean;
  disabled: boolean;
  mode: PlannerMode;
  planner: PlannerInfo;
  onModeChange: (mode: PlannerMode) => void;
}

export function RequestCard({ value, onChange, onSubmit, loading, disabled, mode, planner, onModeChange }: Props) {
  const empty = !value.trim();
  return (
    <Card title="说出需求">
      <TextInput
        value={value}
        onChangeText={onChange}
        placeholder="例如：我想休息"
        placeholderTextColor={colors.muted}
        maxLength={200}
        style={styles.input}
        returnKeyType="done"
        onSubmitEditing={() => !empty && !disabled && onSubmit()}
        accessibilityLabel="需求输入"
      />
      <ModeToggle value={mode} planner={planner} disabled={disabled} onChange={onModeChange} />
      <Text style={styles.note}>
        {mode === 'rule'
          ? '规则模式只支持固定的“休息”场景：输入的文字会被记录，但不做语义理解。'
          : '模型模式会参考这句话调整休息设置；结果仍需你确认后才会执行。'}
      </Text>
      <Button label="生成休息计划" onPress={onSubmit} loading={loading} disabled={disabled || empty} />
    </Card>
  );
}

const styles = StyleSheet.create({
  input: {
    minHeight: 48,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    paddingHorizontal: space.md,
    fontSize: font.body + 1,
    color: colors.ink,
    backgroundColor: colors.surface,
  },
  note: { fontSize: font.small, color: colors.muted },
});

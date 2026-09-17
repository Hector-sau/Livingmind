import { StyleSheet, Text, TextInput } from 'react-native';

import { Button } from '../../components/Button';
import { Card } from '../../components/Card';
import { colors, font, radius, space } from '../../theme/tokens';

interface Props {
  value: string;
  onChange: (v: string) => void;
  onSubmit: () => void;
  loading: boolean;
  disabled: boolean;
}

export function RequestCard({ value, onChange, onSubmit, loading, disabled }: Props) {
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
      <Text style={styles.note}>当前只支持固定的“休息”场景：输入的文字会被记录，但还没有做语义理解。</Text>
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

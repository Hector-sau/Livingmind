import { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';

import { Button } from '../../components/Button';
import type { PlannerInfo, PlannerMode } from '../../services/types';
import { colors, font, radius, space } from '../../theme/tokens';
import { ModeToggle } from '../rest/ModeToggle';

interface Props {
  disabled: boolean;
  sending: boolean;
  mode: PlannerMode;
  planner: PlannerInfo;
  apiMode: 'mock' | 'http';
  onModeChange: (mode: PlannerMode) => void;
  onSend: (text: string) => void;
  onVoice: () => void;
}

const QUICK = ['我想休息', '我想休息，有点热', '想早点睡，灯再暗一点'];

export function Composer({ disabled, sending, mode, planner, apiMode, onModeChange, onSend, onVoice }: Props) {
  const [text, setText] = useState('');
  const send = (value: string) => {
    const v = value.trim();
    if (!v || disabled) return;
    onSend(v);
    setText('');
  };
  return (
    <View style={styles.wrap}>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.chips}>
        {QUICK.map((q) => (
          <Pressable key={q} style={styles.chip} disabled={disabled} onPress={() => send(q)} accessibilityRole="button">
            <Text style={styles.chipText}>{q}</Text>
          </Pressable>
        ))}
      </ScrollView>
      <View style={styles.row}>
        <Pressable
          style={styles.mic}
          onPress={onVoice}
          accessibilityRole="button"
          accessibilityLabel="语音输入（后续接入）"
          testID="mic-button"
        >
          <Text style={styles.micText}>🎙</Text>
        </Pressable>
        <TextInput
          value={text}
          onChangeText={setText}
          placeholder="说说你现在想怎么休息…"
          placeholderTextColor={colors.muted}
          maxLength={200}
          style={styles.input}
          returnKeyType="send"
          onSubmitEditing={() => send(text)}
          accessibilityLabel="需求输入"
          testID="composer-input"
        />
        <Button label="发送" onPress={() => send(text)} loading={sending} disabled={disabled || !text.trim()} testID="composer-send" />
      </View>
      <ModeToggle value={mode} planner={planner} apiMode={apiMode} disabled={disabled} onChange={onModeChange} />
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    gap: space.sm,
    padding: space.md,
    backgroundColor: colors.card,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  chips: { flexDirection: 'row', gap: space.sm },
  chip: {
    paddingHorizontal: space.md,
    paddingVertical: space.xs + 2,
    borderRadius: radius.pill,
    backgroundColor: colors.homeTint,
  },
  chipText: { fontSize: font.small, color: colors.blue, fontWeight: '600' },
  row: { flexDirection: 'row', alignItems: 'center', gap: space.sm },
  mic: {
    width: 48,
    height: 48,
    borderRadius: 24,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.surface,
  },
  micText: { fontSize: 20 },
  input: {
    flex: 1,
    minWidth: 0,
    minHeight: 48,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.pill,
    paddingHorizontal: space.lg,
    fontSize: font.body + 1,
    color: colors.ink,
    backgroundColor: colors.surface,
  },
});

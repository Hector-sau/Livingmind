import { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';

import { Button } from '../../components/Button';
import { Icon } from '../../components/Icon';
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
  onSend: (text: string, wakeTime: '06:30' | '07:00' | '07:30') => void;
  onVoice: () => void;
}

const QUICK = ['我想休息', '我想休息，有点热', '想早点睡，灯再暗一点'];
const WAKE_TIMES = ['06:30', '07:00', '07:30'] as const;

export function Composer({ disabled, sending, mode, planner, apiMode, onModeChange, onSend, onVoice }: Props) {
  const [text, setText] = useState('');
  const [wakeTime, setWakeTime] = useState<(typeof WAKE_TIMES)[number]>('07:00');
  const send = (value: string) => {
    const v = value.trim();
    if (!v || disabled) return;
    onSend(v, wakeTime);
    setText('');
  };
  return (
    <View style={styles.wrap}>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.chips}>
        {QUICK.map((q) => (
          <Pressable
            key={q}
            style={({ pressed }) => [styles.chip, pressed && styles.chipPressed]}
            disabled={disabled}
            onPress={() => send(q)}
            accessibilityRole="button"
          >
            <Icon name="sparkles-outline" size={13} color={colors.blue} />
            <Text style={styles.chipText}>{q}</Text>
          </Pressable>
        ))}
      </ScrollView>
      <View style={styles.wakeRow}>
        <Text style={styles.wakeLabel}>模拟起床</Text>
        {WAKE_TIMES.map((time) => (
          <Pressable
            key={time}
            onPress={() => setWakeTime(time)}
            disabled={disabled}
            accessibilityRole="radio"
            accessibilityState={{ selected: wakeTime === time }}
            testID={`wake-time-${time}`}
            style={[styles.wakeOption, wakeTime === time && styles.wakeOptionSelected]}
          >
            <Text style={[styles.wakeText, wakeTime === time && styles.wakeTextSelected]}>{time}</Text>
          </Pressable>
        ))}
      </View>
      <View style={styles.bar}>
        <Pressable
          style={styles.mic}
          onPress={onVoice}
          accessibilityRole="button"
          accessibilityLabel="语音输入（后续接入）"
          testID="mic-button"
        >
          <Icon name="mic-outline" size={20} color={colors.blue} />
        </Pressable>
        <TextInput
          value={text}
          onChangeText={setText}
          placeholder="说说你现在想怎么休息…"
          placeholderTextColor={colors.faint}
          maxLength={200}
          style={styles.input}
          returnKeyType="send"
          onSubmitEditing={() => send(text)}
          accessibilityLabel="需求输入"
          testID="composer-input"
        />
        <Button
          label="发送"
          icon="arrow-up"
          iconOnly
          onPress={() => send(text)}
          loading={sending}
          disabled={disabled || !text.trim()}
          testID="composer-send"
        />
      </View>
      <ModeToggle value={mode} planner={planner} apiMode={apiMode} disabled={disabled} onChange={onModeChange} />
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    gap: space.sm,
    paddingHorizontal: space.md,
    paddingTop: space.sm,
    paddingBottom: space.md,
    backgroundColor: 'rgba(255,255,255,0.92)',
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  chips: { flexDirection: 'row', gap: space.sm },
  wakeRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  wakeLabel: { fontSize: font.caption, color: colors.muted, fontWeight: '700', marginRight: 2 },
  wakeOption: { paddingHorizontal: 10, paddingVertical: 5, borderRadius: radius.pill, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border },
  wakeOptionSelected: { backgroundColor: colors.homeTint, borderColor: colors.blue },
  wakeText: { fontSize: font.caption, color: colors.muted, fontWeight: '700' },
  wakeTextSelected: { color: colors.blue },
  chip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: space.md,
    paddingVertical: 6,
    borderRadius: radius.pill,
    backgroundColor: colors.card,
    borderWidth: 1,
    borderColor: '#CFE8FA',
  },
  chipPressed: { backgroundColor: colors.homeTint },
  chipText: { fontSize: font.small, color: colors.blue, fontWeight: '600' },
  bar: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.sm,
    backgroundColor: colors.card,
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: '#CFE8FA',
    padding: 4,
    boxShadow: '0px 4px 16px rgba(2, 132, 199, 0.10)',
  },
  mic: {
    width: 44,
    height: 44,
    borderRadius: 22,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.homeTint,
  },
  input: {
    flex: 1,
    minWidth: 0,
    minHeight: 44,
    paddingHorizontal: space.sm,
    fontSize: font.body + 1,
    color: colors.ink,
    outlineStyle: 'none',
  } as object,
});

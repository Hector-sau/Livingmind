import { StyleSheet, Text, View } from 'react-native';

import { Card } from '../../components/Card';
import { Pill } from '../../components/Pill';
import { colors, font, radius, space } from '../../theme/tokens';
import { PlanCard } from '../rest/PlanCard';
import type { Plan } from '../../services/types';
import { resultSummary, type Message } from './conversation';

interface Props {
  message: Message;
  /** Live version of the plan if this card is the current one. */
  livePlan: Plan | null;
  actionable: boolean;
  blockReason: string | null;
  busy: boolean;
  confirmLoading: boolean;
  onConfirm: () => void;
}

const SYSTEM_TONE = {
  info: { bg: colors.homeTint, fg: colors.blue },
  success: { bg: colors.greenTint, fg: colors.green },
  warning: { bg: colors.amberTint, fg: colors.amber },
  error: { bg: colors.redTint, fg: colors.red },
} as const;

const DEVICE_NAME = { light: '灯光', ac: '空调', curtain: '窗帘' } as const;
const UNIT = { light: '%', ac: '°C', curtain: '%' } as const;

export function MessageView({ message, livePlan, actionable, blockReason, busy, confirmLoading, onConfirm }: Props) {
  switch (message.kind) {
    case 'user':
      return (
        <View style={[styles.row, styles.right]}>
          <View style={styles.userBubble}>
            <Text style={styles.userText}>{message.text}</Text>
          </View>
        </View>
      );
    case 'system': {
      const tone = SYSTEM_TONE[message.tone];
      return (
        <View style={[styles.row, styles.center]} testID="system-message">
          <View style={[styles.systemBox, { backgroundColor: tone.bg }]}>
            <Text style={[styles.systemText, { color: tone.fg }]}>{message.text}</Text>
          </View>
        </View>
      );
    }
    case 'plan':
      return (
        <View style={[styles.row, styles.left]}>
          <View style={styles.assistantBlock}>
            <PlanCard
              title="我的建议"
              plan={livePlan ?? message.plan}
              results={[]}
              blockReason={blockReason}
              loading={confirmLoading}
              disabled={busy}
              onConfirm={onConfirm}
              actionable={actionable}
            />
          </View>
        </View>
      );
    case 'result':
      return (
        <View style={[styles.row, styles.left]} testID="result-card">
          <View style={styles.assistantBlock}>
            <Card title={message.repeated ? '这个计划之前已执行' : '已执行'} right={<Pill label={resultSummary(message.results)} tone="green" />}>
              {message.results.map((r) => (
                <View key={r.actionId} style={styles.resultRow}>
                  <Text style={styles.resultName}>{DEVICE_NAME[r.device]}</Text>
                  <Text style={styles.resultValue}>
                    {r.outcome === 'succeeded' ? `${r.observedValue}${UNIT[r.device]}` : `未执行：${r.reason ?? r.outcome}`}
                  </Text>
                </View>
              ))}
              <Text style={styles.note}>
                {message.deviceState.source === 'virtual_device' ? '数值读回自后端虚拟设备' : '前端模拟设备'}，不代表真实硬件。
              </Text>
            </Card>
          </View>
        </View>
      );
  }
}

export function AssistantText({ text }: { text: string }) {
  return (
    <View style={[styles.row, styles.left]}>
      <View style={styles.assistantBubble}>
        <Text style={styles.assistantText}>{text}</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row' },
  right: { justifyContent: 'flex-end' },
  left: { justifyContent: 'flex-start' },
  center: { justifyContent: 'center' },
  userBubble: {
    maxWidth: '80%',
    backgroundColor: colors.blue,
    borderRadius: radius.lg,
    borderBottomRightRadius: 4,
    paddingHorizontal: space.lg,
    paddingVertical: space.md,
  },
  userText: { color: '#fff', fontSize: font.body + 1 },
  assistantBubble: {
    maxWidth: '85%',
    backgroundColor: colors.card,
    borderRadius: radius.lg,
    borderBottomLeftRadius: 4,
    borderWidth: 1,
    borderColor: colors.border,
    paddingHorizontal: space.lg,
    paddingVertical: space.md,
  },
  assistantText: { color: colors.ink, fontSize: font.body + 1, lineHeight: 22 },
  assistantBlock: { width: '100%', maxWidth: 560 },
  systemBox: { maxWidth: '92%', borderRadius: radius.md, paddingHorizontal: space.md, paddingVertical: space.sm },
  systemText: { fontSize: font.small, fontWeight: '600', textAlign: 'center' },
  resultRow: { flexDirection: 'row', justifyContent: 'space-between' },
  resultName: { fontSize: font.body, color: colors.muted },
  resultValue: { fontSize: font.body, color: colors.ink, fontWeight: '600' },
  note: { fontSize: font.caption, color: colors.muted },
});

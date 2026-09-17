import { LinearGradient } from 'expo-linear-gradient';
import { Image, StyleSheet, Text, View } from 'react-native';

import { Card } from '../../components/Card';
import { DeviceIcon, Icon, type IconName } from '../../components/Icon';
import { FadeIn } from '../../components/motion';
import { Pill } from '../../components/Pill';
import type { Plan } from '../../services/types';
import { colors, font, gradients, radius, space } from '../../theme/tokens';
import { PlanCard } from '../rest/PlanCard';
import { resultSummary, type Message } from './conversation';

const MARK = require('../../assets/logo-mark.png');

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

const SYSTEM_TONE: Record<string, { bg: string; fg: string; icon: IconName }> = {
  info: { bg: colors.homeTint, fg: colors.blue, icon: 'information-circle-outline' },
  success: { bg: colors.greenTint, fg: colors.green, icon: 'checkmark-circle-outline' },
  warning: { bg: colors.amberTint, fg: colors.amber, icon: 'cloud-offline-outline' },
  error: { bg: colors.redTint, fg: colors.red, icon: 'alert-circle-outline' },
};

const DEVICE_NAME = { light: '灯光', ac: '空调', curtain: '窗帘' } as const;
const UNIT = { light: '%', ac: '°C', curtain: '%' } as const;

function AssistantAvatar() {
  return (
    <View style={styles.avatar}>
      <Image source={MARK} style={styles.avatarImg} />
    </View>
  );
}

export function MessageView({ message, livePlan, actionable, blockReason, busy, confirmLoading, onConfirm }: Props) {
  switch (message.kind) {
    case 'user':
      return (
        <FadeIn style={[styles.row, styles.right]}>
          <LinearGradient colors={[...gradients.sky]} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={styles.userBubble}>
            <Text style={styles.userText}>{message.text}</Text>
          </LinearGradient>
        </FadeIn>
      );
    case 'assistant':
      return <AssistantText text={message.text} />;
    case 'system': {
      const tone = SYSTEM_TONE[message.tone];
      return (
        <FadeIn style={[styles.row, styles.center]}>
          <View testID="system-message" style={[styles.systemBox, { backgroundColor: tone.bg }]}>
            <Icon name={tone.icon} size={16} color={tone.fg} />
            <Text style={[styles.systemText, { color: tone.fg }]}>{message.text}</Text>
          </View>
        </FadeIn>
      );
    }
    case 'plan':
      return (
        <FadeIn style={[styles.row, styles.left]}>
          <AssistantAvatar />
          <View style={styles.assistantBlock} testID="plan-message">
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
        </FadeIn>
      );
    case 'result':
      return (
        <FadeIn style={[styles.row, styles.left]}>
          <AssistantAvatar />
          <View style={styles.assistantBlock} testID="result-card">
            <Card
              title={message.repeated ? '这个计划之前已执行' : '已为你调整好'}
              icon="checkmark-done-outline"
              right={<Pill label={resultSummary(message.results)} tone="green" />}
            >
              <View style={styles.results}>
                {message.results.map((r) => (
                  <View key={r.actionId} style={styles.resultTile}>
                    <DeviceIcon device={r.device} size={18} color={colors.blue} />
                    <Text style={styles.resultName}>{DEVICE_NAME[r.device]}</Text>
                    <Text style={styles.resultValue}>
                      {r.outcome === 'succeeded' ? `${r.observedValue}${UNIT[r.device]}` : `未执行`}
                    </Text>
                    {r.outcome !== 'succeeded' ? <Text style={styles.resultReason}>{r.reason ?? r.outcome}</Text> : null}
                  </View>
                ))}
              </View>
              <Text style={styles.note}>
                {message.deviceState.source === 'virtual_device' ? '数值读回自后端虚拟设备' : '前端模拟设备'}，不代表真实硬件。
              </Text>
            </Card>
          </View>
        </FadeIn>
      );
  }
}

export function AssistantText({ text, testID = 'assistant-message' }: { text: string; testID?: string }) {
  return (
    <FadeIn style={[styles.row, styles.left]}>
      <AssistantAvatar />
      <View style={styles.assistantBubble} testID={testID}>
        <Text style={styles.assistantText}>{text}</Text>
      </View>
    </FadeIn>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', gap: space.sm, alignItems: 'flex-start' },
  right: { justifyContent: 'flex-end' },
  left: { justifyContent: 'flex-start' },
  center: { justifyContent: 'center' },
  avatar: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: colors.card,
    alignItems: 'center',
    justifyContent: 'center',
    boxShadow: '0px 2px 8px rgba(2, 132, 199, 0.15)',
  },
  avatarImg: { width: 24, height: 24 },
  userBubble: {
    maxWidth: '80%',
    borderRadius: radius.lg,
    borderBottomRightRadius: 6,
    paddingHorizontal: space.lg,
    paddingVertical: space.md,
  },
  userText: { color: '#fff', fontSize: font.body + 1, fontWeight: '500' },
  assistantBubble: {
    maxWidth: '82%',
    flexShrink: 1,
    backgroundColor: colors.card,
    borderRadius: radius.lg,
    borderTopLeftRadius: 6,
    paddingHorizontal: space.lg,
    paddingVertical: space.md,
    boxShadow: '0px 4px 14px rgba(2, 132, 199, 0.07)',
  },
  assistantText: { color: colors.ink, fontSize: font.body + 1, lineHeight: 23 },
  assistantBlock: { flex: 1, maxWidth: 560 },
  systemBox: {
    maxWidth: '92%',
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    borderRadius: radius.pill,
    paddingHorizontal: space.md,
    paddingVertical: 6,
  },
  systemText: { fontSize: font.small, fontWeight: '600', flexShrink: 1 },
  results: { flexDirection: 'row', flexWrap: 'wrap', gap: space.sm },
  resultTile: {
    flexGrow: 1,
    flexBasis: 90,
    backgroundColor: colors.skyMist,
    borderRadius: radius.md,
    padding: space.md,
    gap: 2,
  },
  resultName: { fontSize: font.caption, color: colors.muted, marginTop: 4 },
  resultValue: { fontSize: 20, color: colors.ink, fontWeight: '800' },
  resultReason: { fontSize: font.caption, color: colors.red },
  note: { fontSize: font.caption, color: colors.muted },
});

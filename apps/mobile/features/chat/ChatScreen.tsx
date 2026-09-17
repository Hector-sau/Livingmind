import { useEffect, useRef } from 'react';
import { ScrollView, StyleSheet, Text, useWindowDimensions, View } from 'react-native';

import type { LivingMindApi } from '../../services';
import { colors, font, space, SPLIT_BREAKPOINT } from '../../theme/tokens';
import { DevicePanel } from '../devices/DevicePanel';
import type { RestFlow } from '../rest/useRestFlow';
import { actionablePlanId, greeting, messageId, resultSummary, type ConversationAction, type Message } from './conversation';
import { Composer } from './Composer';
import { AssistantText, MessageView } from './MessageView';
import { ServiceStrip } from './ServiceStrip';

interface Props {
  api: LivingMindApi;
  flow: RestFlow;
  messages: Message[];
  dispatch: (a: ConversationAction) => void;
}

export function ChatScreen({ api, flow, messages, dispatch }: Props) {
  const { state, person, activeService, blockReason, actions } = flow;
  const { width } = useWindowDimensions();
  const wide = width >= SPLIT_BREAKPOINT;
  const scroller = useRef<ScrollView>(null);
  const busy = state.busy !== null;
  const personId = state.personId ?? 'none';

  useEffect(() => {
    const t = setTimeout(() => scroller.current?.scrollToEnd({ animated: true }), 50);
    return () => clearTimeout(t);
  }, [messages.length]);

  const now = () => new Date().toISOString();
  const push = (message: Message) => dispatch({ type: 'append', personId, message });
  const system = (text: string, tone: 'info' | 'success' | 'warning' | 'error') =>
    push({ kind: 'system', id: messageId(), text, tone, at: now() });

  const send = async (text: string) => {
    push({ kind: 'user', id: messageId(), text, at: now() });
    const res = await actions.createPlan(text);
    if (res.ok) push({ kind: 'plan', id: messageId(), plan: res.value, at: now() });
    else system(`没能生成计划：${res.error.message}`, res.error.connectivity ? 'warning' : 'error');
  };

  const confirm = async () => {
    const res = await actions.confirm();
    if (res.ok) {
      const r = res.value;
      push({ kind: 'result', id: messageId(), plan: r.plan, results: r.results, deviceState: r.deviceState, repeated: r.repeated, at: now() });
    } else {
      system(`没有执行：${res.error.message}`, res.error.connectivity ? 'warning' : 'error');
    }
  };

  const injectEvent = async (temp: number) => {
    const res = await actions.injectEvent(temp);
    if (!res.ok) return system(`模拟事件失败：${res.error.message}`, 'error');
    const r = res.value;
    if (r.outcome === 'adjusted') {
      system(`模拟事件 · 室温 ${temp}°C → 已自动调整：${r.plan?.summary ?? ''}（${resultSummary(r.results)}）`, 'success');
    } else {
      system(`模拟事件 · 室温 ${temp}°C → 未调整：${r.reason ?? ''}`, 'info');
    }
  };

  const stop = async () => {
    const res = await actions.stop();
    if (res.ok) system('休息服务已停止，设备保持当前状态；之后的事件不会再触发调整', 'info');
    else system(`停止失败：${res.error.message}`, 'error');
  };

  const currentPlanId = actionablePlanId(messages, state.plan?.planId ?? null);
  const data = state.data!;

  const conversation = (
    <View style={styles.chatColumn}>
      {!wide ? (
        <View style={styles.stripWrap}>
          <ServiceStrip
            service={activeService}
            acTargetTempC={state.deviceState?.acTargetTempC ?? null}
            busy={busy}
            eventLoading={state.busy === 'event'}
            stopLoading={state.busy === 'stop'}
            onInjectEvent={injectEvent}
            onStop={stop}
          />
        </View>
      ) : null}
      <ScrollView ref={scroller} contentContainerStyle={styles.messages} keyboardShouldPersistTaps="handled">
        <AssistantText text={greeting(person?.name ?? '', person?.isGuest ?? false)} />
        {messages.map((m) => (
          <MessageView
            key={m.id}
            message={m}
            livePlan={m.kind === 'plan' && state.plan?.planId === m.plan.planId ? state.plan : null}
            actionable={m.kind === 'plan' && m.plan.planId === currentPlanId}
            blockReason={blockReason}
            busy={busy}
            confirmLoading={state.busy === 'confirm'}
            onConfirm={confirm}
          />
        ))}
        {state.busy === 'plan' ? <AssistantText text={state.mode === 'model' ? '正在理解你的需求…' : '正在生成计划…'} /> : null}
      </ScrollView>
      <Composer
        disabled={busy || !state.personId}
        sending={state.busy === 'plan'}
        mode={state.mode}
        planner={data.planner}
        apiMode={api.mode}
        onModeChange={actions.setMode}
        onSend={send}
        onVoice={() => system('语音输入后续接入，现在请先打字', 'info')}
      />
    </View>
  );

  if (!wide) return conversation;

  return (
    <View style={styles.wide}>
      {conversation}
      <ScrollView style={styles.side} contentContainerStyle={styles.sideContent}>
        <Text style={styles.sideTitle}>房间现在</Text>
        <ServiceStrip
          service={activeService}
          acTargetTempC={state.deviceState?.acTargetTempC ?? null}
          busy={busy}
          eventLoading={state.busy === 'event'}
          stopLoading={state.busy === 'stop'}
          onInjectEvent={injectEvent}
          onStop={stop}
        />
        <DevicePanel
          state={state.deviceState}
          stale={state.deviceStale}
          loading={state.busy === 'refresh'}
          disabled={busy}
          onRefresh={actions.refresh}
        />
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  wide: { flex: 1, flexDirection: 'row' },
  chatColumn: { flex: 1, backgroundColor: colors.surface },
  stripWrap: { paddingHorizontal: space.md, paddingTop: space.md },
  messages: { padding: space.lg, gap: space.md },
  side: { width: 340, flexGrow: 0, borderLeftWidth: 1, borderLeftColor: colors.border, backgroundColor: colors.surface },
  sideContent: { padding: space.lg, gap: space.md },
  sideTitle: { fontSize: font.section, fontWeight: '700', color: colors.ink },
});

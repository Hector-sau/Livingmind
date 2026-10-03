import { useEffect, useRef, useState } from 'react';
import { ScrollView, StyleSheet, Text, useWindowDimensions, View } from 'react-native';

import { EmptyState } from '../../components/EmptyState';
import { FadeIn } from '../../components/motion';
import type { LivingMindApi } from '../../services';
import { colors, font, space, SPLIT_BREAKPOINT } from '../../theme/tokens';
import { DevicePanel } from '../devices/DevicePanel';
import type { RestFlow } from '../rest/useRestFlow';
import { actionablePlanId, greeting, messageId, resultSummary, type ConversationAction, type Message } from './conversation';
import { Composer } from './Composer';
import { AssistantText, MessageView } from './MessageView';
import { ServiceStrip } from './ServiceStrip';
import { advanceMessages, AUTO_PLAY_MS } from '../night/schedule';
import { needsSourceBadge, sourceLabel, type TranscriptSource } from '../voice/machine';
import { useVoice } from '../voice/useVoice';
import { VoiceSheet } from '../voice/VoiceSheet';

/** Offered inside the voice sheet when this build has no recogniser to produce a transcript. */
const VOICE_EXAMPLES = ['我想休息', '把灯调到 20%', '把空调调到 24 度', '卧室现在几度'] as const;

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
  const checking = useRef(new Set<string>());
  const [checkingIds, setCheckingIds] = useState<string[]>([]);

  const reconcile = async (message: Message) => {
    if (message.kind !== 'result' || message.plan.personId !== personId || !state.data || checking.current.has(message.id)) return;
    checking.current.add(message.id);
    setCheckingIds([...checking.current]);
    const context = { accountId: state.data.account.accountId, personId, spaceId: message.plan.spaceId };
    try {
      for (const result of message.results.filter((r) => r.outcome === 'unknown')) {
        const receipt = await api.reconcileAction(result.actionId, context);
        if (receipt.actionId !== result.actionId) throw new Error('回执与请求的动作不一致，保留未知状态');
        dispatch({ type: 'reconcileResult', personId, messageId: message.id, receipt });
      }
    } catch (error) {
      dispatch({ type: 'reconcileNote', personId, messageId: message.id,
        text: `暂时无法核对：${error instanceof Error ? error.message : '请求失败'}。没有重发设备动作。` });
    } finally {
      checking.current.delete(message.id);
      setCheckingIds([...checking.current]);
    }
  };

  useEffect(() => {
    const t = setTimeout(() => scroller.current?.scrollToEnd({ animated: true }), 50);
    return () => clearTimeout(t);
  }, [messages.length]);

  const now = () => new Date().toISOString();
  const push = (message: Message) => dispatch({ type: 'append', personId, message });
  const system = (text: string, tone: 'info' | 'success' | 'warning' | 'error') =>
    push({ kind: 'system', id: messageId(), text, tone, at: now() });

  const send = async (
    text: string,
    wakeTime: '06:30' | '07:00' | '07:30',
    voiceSource: TranscriptSource | null = null,
  ) => {
    const badge = voiceSource && needsSourceBadge(voiceSource) ? sourceLabel(voiceSource) : null;
    push({ kind: 'user', id: messageId(), text, badge, at: now() });
    const res = await actions.sendMessage(text, wakeTime);
    if (!res.ok) {
      if (voiceSource) voice.settle(false, null);
      return system(`没能处理：${res.error.message}`, res.error.connectivity ? 'warning' : 'error');
    }
    const reply = res.value;
    if (reply.plan) push({ kind: 'plan', id: messageId(), plan: reply.plan, at: now() });
    else push({ kind: 'assistant', id: messageId(), text: reply.text, trace: reply.trace, at: now() });
    // Speak short answers and clarifying questions; a plan is read on screen, not aloud.
    if (voiceSource) voice.settle(true, reply.plan ? null : reply.text);
  };

  const voice = useVoice();
  const wakeTimeRef = useRef<'06:30' | '07:00' | '07:30'>('07:00');

  useEffect(() => {
    if (voice.state.status !== 'sending' || !voice.state.transcript) return;
    const { transcript, source } = voice.state;
    void send(transcript, wakeTimeRef.current, source);
    // Only the transition into `sending` starts a request.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [voice.state.status]);

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
    if (res.stale) return;
    if (!res.ok) return system(`模拟事件失败：${res.error.message}`, 'error');
    const r = res.value;
    if (r.outcome === 'adjusted') {
      system(`模拟事件 · 室温 ${temp}°C → 已自动调整：${r.plan?.summary ?? ''}（${resultSummary(r.results)}）`, 'success');
    } else {
      system(`模拟事件 · 室温 ${temp}°C → 未调整：${r.reason ?? ''}`, 'info');
    }
  };

  const advance = async () => {
    const res = await actions.advanceClock(null);
    if (res.stale) return;
    if (!res.ok) {
      setAutoPlay(false);
      return system(`快进失败：${res.error.message}`, res.error.connectivity ? 'warning' : 'error');
    }
    advanceMessages(res.value).forEach((m) => system(m.text, m.tone));
    if (res.value.service.status !== 'active') setAutoPlay(false);
  };

  const simulateSleep = async () => {
    const res = await actions.simulateSleep();
    if (res.stale) return;
    if (!res.ok) return system(`模拟入睡失败：${res.error.message}`, res.error.connectivity ? 'warning' : 'error');
    system(res.value.note ?? '已模拟入睡', 'success');
  };

  // Auto-play: one simulated step every few seconds while the service is active.
  const [autoPlay, setAutoPlay] = useState(false);
  const advanceRef = useRef(advance);
  advanceRef.current = advance;
  const running = activeService !== null;
  useEffect(() => {
    if (!running) setAutoPlay(false);
  }, [running]);
  useEffect(() => {
    if (!autoPlay || !running || busy) return;
    const t = setTimeout(() => void advanceRef.current(), AUTO_PLAY_MS);
    return () => clearTimeout(t);
  }, [autoPlay, running, busy]);

  const stop = async () => {
    setAutoPlay(false);
    const res = await actions.stop();
    if (res.ok) system(res.value.warning ?? '休息服务已停止，设备保持当前状态；未执行的整晚步骤已取消，之后的事件不会再触发调整', res.value.warning ? 'warning' : 'info');
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
            clockLoading={state.busy === 'clock'}
            autoPlay={autoPlay}
            onAdvance={() => void advance()}
            onSimulateSleep={() => void simulateSleep()}
            onToggleAuto={() => setAutoPlay((v) => !v)}
          />
        </View>
      ) : null}
      <ScrollView ref={scroller} contentContainerStyle={styles.messages} keyboardShouldPersistTaps="handled">
        <AssistantText text={greeting(person?.name ?? '', person?.isGuest ?? false)} />
        {messages.length === 0 && state.busy !== 'plan' ? (
          <FadeIn>
            <EmptyState
              icon="chatbubbles-outline"
              title="从一句话开始"
              hint="比如“我想休息一下”“把空调调到 24 度”，或点下方的快捷短语。"
              testID="chat-empty"
            />
          </FadeIn>
        ) : null}
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
            onReconcile={api.mode === 'http' ? () => void reconcile(m) : undefined}
            reconcileLoading={checkingIds.includes(m.id)}
          />
        ))}
        {state.busy === 'plan' ? (
          <AssistantText testID="assistant-typing" text={state.mode === 'model' ? '正在理解你的需求…' : '正在思考…'} />
        ) : null}
      </ScrollView>
      <VoiceSheet
        state={voice.state}
        asrConnected={voice.asrConnected}
        examples={VOICE_EXAMPLES}
        onExample={(text) => voice.submit(text, 'example')}
        onCancel={voice.cancel}
        onSkipSpeech={voice.skipSpeech}
      />
      <Composer
        disabled={busy || !state.personId}
        sending={state.busy === 'plan'}
        mode={state.mode}
        planner={data.planner}
        apiMode={api.mode}
        onModeChange={actions.setMode}
        onSend={send}
        onVoice={voice.press}
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
          clockLoading={state.busy === 'clock'}
          autoPlay={autoPlay}
          onAdvance={() => void advance()}
          onSimulateSleep={() => void simulateSleep()}
          onToggleAuto={() => setAutoPlay((v) => !v)}
        />
        <DevicePanel
          state={state.deviceState}
          stale={state.deviceStale}
          loading={state.busy === 'refresh'}
          disabled={busy}
          pending={state.devicePending}
          failures={state.deviceFailure}
          undoWindow={state.undoWindow}
          undoBusy={state.busy === 'undo'}
          onRefresh={actions.refresh}
          onControl={(device, value) => void actions.controlDevice(device, value)}
          onUndo={() => void actions.undoControl()}
          onUndoExpired={actions.dismissUndo}
          vertical
        />
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  wide: { flex: 1, flexDirection: 'row' },
  chatColumn: { flex: 1 },
  stripWrap: { paddingHorizontal: space.md, paddingTop: space.md },
  messages: { padding: space.lg, gap: space.lg, maxWidth: 820, width: '100%', alignSelf: 'center' },
  side: { width: 340, flexGrow: 0, borderLeftWidth: 1, borderLeftColor: colors.border, backgroundColor: 'rgba(255,255,255,0.55)' },
  sideContent: { padding: space.lg, gap: space.md },
  sideTitle: { fontSize: font.section, fontWeight: '700', color: colors.ink },
});

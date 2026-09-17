import { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { Button } from '../../components/Button';
import { Card } from '../../components/Card';
import { DeviceIcon, Icon } from '../../components/Icon';
import { Pill, type PillTone } from '../../components/Pill';
import type { ActionResult, Plan } from '../../services/types';
import { colors, font, radius, space } from '../../theme/tokens';
import { PLAN_SOURCE_LABEL, PLAN_STATUS_LABEL } from '../../utils/format';
import { TraceView } from '../agents/TraceView';
import { EnergyLine } from '../energy/EnergyLine';
import { NightTimeline } from '../night/NightTimeline';

interface Props {
  plan: Plan | null;
  results: ActionResult[];
  blockReason: string | null;
  loading: boolean;
  disabled: boolean;
  onConfirm: () => void;
  /** False for history cards in the chat: no confirm button. */
  actionable?: boolean;
  title?: string;
}

const SOURCE_TONE: Record<Plan['source'], PillTone> = {
  rule: 'violet',
  model: 'teal',
  rule_fallback: 'amber',
  frontend_mock: 'amber',
};

const STATUS_TONE: Record<Plan['status'], PillTone> = {
  proposed: 'blue',
  executed: 'green',
  expired: 'amber',
  invalidated: 'red',
};

function describeGeneration(plan: Plan): string {
  const g = plan.generation;
  const requested = g.modeRequested === 'model' ? '请求模型' : '请求规则';
  if (plan.source === 'model') return `${requested} · ${g.provider}/${g.model} · ${g.latencyMs} ms`;
  if (plan.source === 'rule_fallback') return `${requested} · 改用规则 · ${g.latencyMs} ms`;
  if (plan.source === 'frontend_mock') return `${requested} · 前端本地生成`;
  return `${requested} · 后端规则 · ${g.latencyMs} ms`;
}

export function PlanCard({ plan, results, blockReason, loading, disabled, onConfirm, actionable = true, title = '休息计划' }: Props) {
  if (!plan) {
    return (
      <Card title={title} icon="moon-outline">
        <Text style={styles.empty}>还没有计划。说出你的需求后，这里会显示将要执行的设备动作。</Text>
      </Card>
    );
  }
  const resultById = new Map(results.map((r) => [r.actionId, r]));
  return (
    <Card
      title={plan.scenario === 'device_command' ? '设备指令' : title}
      icon={plan.scenario === 'device_command' ? 'hardware-chip-outline' : 'sparkles-outline'}
      right={<Pill label={PLAN_STATUS_LABEL[plan.status]} tone={STATUS_TONE[plan.status]} />}>
      <Text style={styles.summary}>{plan.summary}</Text>
      <View style={styles.meta}>
        <Pill label={PLAN_SOURCE_LABEL[plan.source]} tone={SOURCE_TONE[plan.source]} />
        <Text style={styles.generation}>{describeGeneration(plan)}</Text>
      </View>
      {plan.generation.fallbackReason ? (
        <View style={styles.fallbackBox}>
          <Text style={styles.fallback}>默认方案 / 规则降级：{plan.generation.fallbackReason}</Text>
        </View>
      ) : null}
      <View style={styles.list}>
        {plan.actions.map((a) => {
          const r = resultById.get(a.actionId);
          return (
            <View key={a.actionId} style={styles.action}>
              <View style={styles.actionIcon}>
                <DeviceIcon device={a.device} size={16} color={colors.blue} />
              </View>
              <Text style={styles.actionText}>{a.label}</Text>
              {r ? (
                <Pill
                  label={r.outcome === 'succeeded' ? `已执行 · 回读 ${r.observedValue}` : `${r.outcome}：${r.reason ?? ''}`}
                  tone={r.outcome === 'succeeded' ? 'green' : 'red'}
                />
              ) : null}
            </View>
          );
        })}
      </View>
      {plan.energy ? <EnergyLine advice={plan.energy} /> : null}
      {plan.schedule?.length ? <SchedulePreview plan={plan} /> : null}
      <View style={styles.notes}>
        {plan.notes.map((n) => (
          <Text key={n} style={styles.note}>
            {n}
          </Text>
        ))}
        <Text style={styles.note}>“{plan.utterance}”</Text>
      </View>
      <TraceView trace={plan.trace ?? []} />
      {plan.status === 'proposed' && !actionable ? <Text style={styles.note}>这是较早的计划，已被新的计划替代。</Text> : null}
      {plan.status === 'proposed' && actionable ? (
        <>
          {blockReason ? <Text style={styles.block}>无法执行：{blockReason}</Text> : null}
          <Button
            label="确认执行"
            icon="checkmark-circle-outline"
            onPress={onConfirm}
            loading={loading}
            disabled={disabled || !!blockReason}
            testID="confirm-plan"
          />
        </>
      ) : null}
    </Card>
  );
}

/** The overnight schedule is confirmed together with the plan, so it is shown before confirming. */
function SchedulePreview({ plan }: { plan: Plan }) {
  const [open, setOpen] = useState(false);
  const steps = plan.schedule ?? [];
  return (
    <View style={styles.schedule}>
      <Pressable style={styles.scheduleToggle} onPress={() => setOpen((v) => !v)} accessibilityRole="button" testID="schedule-toggle">
        <Icon name="moon-outline" size={15} color={colors.blue} />
        <Text style={styles.scheduleText}>
          {open ? '收起整晚安排' : `整晚安排：${steps[0].at} 起 ${steps.length} 步，${steps[steps.length - 1].at} 唤醒（模拟时钟）`}
        </Text>
        <Icon name={open ? 'chevron-up' : 'chevron-down'} size={14} color={colors.blue} />
      </Pressable>
      {open ? <NightTimeline steps={steps} testID="plan-schedule" /> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  schedule: { gap: space.sm },
  scheduleToggle: { flexDirection: 'row', alignItems: 'center', gap: 6, alignSelf: 'flex-start', paddingVertical: 4, flexShrink: 1 },
  scheduleText: { fontSize: font.small, color: colors.blue, fontWeight: '700', flexShrink: 1 },
  empty: { fontSize: font.body, color: colors.muted },
  summary: { fontSize: font.body + 1, color: colors.ink, fontWeight: '700', lineHeight: 22 },
  meta: { flexDirection: 'row', alignItems: 'center', gap: space.sm, flexWrap: 'wrap' },
  generation: { fontSize: font.caption, color: colors.muted },
  fallbackBox: { backgroundColor: colors.amberTint, borderRadius: radius.sm, padding: space.sm },
  fallback: { fontSize: font.small, color: colors.amber, fontWeight: '700' },
  list: { gap: space.sm },
  action: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.sm,
    flexWrap: 'wrap',
    backgroundColor: colors.skyMist,
    borderRadius: radius.sm,
    paddingHorizontal: space.md,
    paddingVertical: space.sm,
  },
  actionIcon: { width: 26, height: 26, borderRadius: 13, backgroundColor: colors.card, alignItems: 'center', justifyContent: 'center' },
  actionText: { fontSize: font.body, color: colors.ink, flex: 1, minWidth: 120 },
  notes: { gap: 2 },
  note: { fontSize: font.caption, color: colors.muted },
  block: { fontSize: font.small, color: colors.amber, fontWeight: '700' },
});

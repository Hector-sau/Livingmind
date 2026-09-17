import { StyleSheet, Text, View } from 'react-native';

import { Button } from '../../components/Button';
import { Card } from '../../components/Card';
import { Pill, type PillTone } from '../../components/Pill';
import type { ActionResult, Plan } from '../../services/types';
import { colors, font, space } from '../../theme/tokens';
import { PLAN_SOURCE_LABEL, PLAN_STATUS_LABEL } from '../../utils/format';

interface Props {
  plan: Plan | null;
  results: ActionResult[];
  blockReason: string | null;
  loading: boolean;
  disabled: boolean;
  onConfirm: () => void;
}

const SOURCE_TONE: Record<Plan['source'], PillTone> = {
  rule: 'violet',
  model: 'green',
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

export function PlanCard({ plan, results, blockReason, loading, disabled, onConfirm }: Props) {
  if (!plan) {
    return (
      <Card title="休息计划">
        <Text style={styles.empty}>还没有计划。选择人物并说出需求后，这里会显示将要执行的设备动作。</Text>
      </Card>
    );
  }
  const resultById = new Map(results.map((r) => [r.actionId, r]));
  return (
    <Card title="休息计划" right={<Pill label={PLAN_STATUS_LABEL[plan.status]} tone={STATUS_TONE[plan.status]} />}>
      <View style={styles.meta}>
        <Pill label={PLAN_SOURCE_LABEL[plan.source]} tone={SOURCE_TONE[plan.source]} />
        <Text style={styles.utterance}>“{plan.utterance}”</Text>
      </View>
      <Text style={styles.generation}>{describeGeneration(plan)}</Text>
      {plan.generation.fallbackReason ? (
        <Text style={styles.fallback}>默认方案 / 规则降级：{plan.generation.fallbackReason}</Text>
      ) : null}
      <Text style={styles.summary}>{plan.summary}</Text>
      <View style={styles.list}>
        {plan.actions.map((a) => {
          const r = resultById.get(a.actionId);
          return (
            <View key={a.actionId} style={styles.action}>
              <Text style={styles.actionText}>• {a.label}</Text>
              {r ? (
                <Pill
                  label={r.outcome === 'succeeded' ? `已执行，回读 ${r.observedValue}` : `${r.outcome}：${r.reason ?? ''}`}
                  tone={r.outcome === 'succeeded' ? 'green' : 'red'}
                />
              ) : null}
            </View>
          );
        })}
      </View>
      {plan.notes.map((n) => (
        <Text key={n} style={styles.note}>
          {n}
        </Text>
      ))}
      {plan.status === 'proposed' ? (
        <>
          {blockReason ? <Text style={styles.block}>无法执行：{blockReason}</Text> : null}
          <Button
            label="确认执行"
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

const styles = StyleSheet.create({
  empty: { fontSize: font.body, color: colors.muted },
  meta: { flexDirection: 'row', alignItems: 'center', gap: space.sm, flexWrap: 'wrap' },
  utterance: { fontSize: font.body, color: colors.ink, fontStyle: 'italic' },
  summary: { fontSize: font.body, color: colors.ink, fontWeight: '600' },
  generation: { fontSize: font.caption, color: colors.muted },
  fallback: { fontSize: font.small, color: colors.amber, fontWeight: '600' },
  list: { gap: space.sm },
  action: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: space.sm, flexWrap: 'wrap' },
  actionText: { fontSize: font.body, color: colors.ink },
  note: { fontSize: font.caption, color: colors.muted },
  block: { fontSize: font.small, color: colors.amber, fontWeight: '600' },
});

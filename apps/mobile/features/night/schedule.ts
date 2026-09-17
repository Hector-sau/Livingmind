// Pure helpers for the overnight schedule (simulated clock). No timers here.
import type { AdvanceClockResponse, ScheduledStep, Service } from '../../services/types';

export const STEP_STATUS_LABEL: Record<ScheduledStep['status'], string> = {
  pending: '待执行',
  running: '执行中',
  done: '已执行',
  cancelled: '已取消',
};

export const PHASE_LABEL: Record<ScheduledStep['phase'], string> = {
  sleep: '入睡',
  deep: '深夜',
  wake: '唤醒',
};

/** Auto-play advances one step every few seconds; the clock itself is still simulated. */
export const AUTO_PLAY_MS = 2500;

export function nextPendingStep(service: Service | null): ScheduledStep | null {
  return service?.schedule.find((s) => s.status === 'pending') ?? null;
}

export function scheduleProgress(service: Service | null): { done: number; total: number } {
  const steps = service?.schedule ?? [];
  return { done: steps.filter((s) => s.status === 'done').length, total: steps.length };
}

/** Chat lines for one clock advance, oldest first. */
export function advanceMessages(res: AdvanceClockResponse): { text: string; tone: 'info' | 'success' | 'warning' }[] {
  const out: { text: string; tone: 'info' | 'success' | 'warning' }[] = [];
  if (res.executed.length === 0) {
    out.push({ text: `模拟时间 ${res.service.nightClock} · ${res.note ?? '没有到点的步骤'}`, tone: 'info' });
  }
  for (const step of res.executed) {
    const labels = step.actions.map((a) => a.label).join('、');
    const state = step.status === 'done' ? '' : `（${STEP_STATUS_LABEL[step.status]}）`;
    out.push({ text: `模拟时间 ${step.at} · ${step.title}${labels ? `：${labels}` : ''}${state}`, tone: step.status === 'done' ? 'success' : 'info' });
  }
  if (res.service.status === 'completed') {
    out.push({ text: `${res.service.nightClock} 唤醒完成，整晚服务已结束，设备保持当前状态`, tone: 'success' });
  } else if (res.service.status === 'failed') {
    out.push({ text: '整晚安排执行失败，设备保持当前状态，服务已结束', tone: 'warning' });
  }
  return out;
}

import type { Plan, Service } from '../../services/types';

/**
 * Why the current plan cannot be confirmed (null = can confirm).
 * UI hint only: the backend enforces the same rules.
 */
export function planBlockReason(
  plan: Plan | null,
  activeService: Service | null,
  personId: string | null,
  now: Date = new Date(),
): string | null {
  if (!plan) return '还没有计划';
  if (plan.personId !== personId) return '计划属于其他人物，请重新生成';
  if (plan.status === 'executed') return '计划已执行';
  if (plan.status === 'expired' || now.getTime() > Date.parse(plan.expiresAt)) return '计划已过期，请重新生成';
  if (plan.status === 'invalidated') return '计划已失效，请重新生成';
  if (activeService) return '已有运行中的服务，请先停止';
  return null;
}

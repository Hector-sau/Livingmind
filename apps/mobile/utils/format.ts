import type { ActivitySource, PlanSource, PlanStatus } from '../services/types';

export function formatTime(iso: string): string {
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

export const PLAN_SOURCE_LABEL: Record<PlanSource, string> = {
  rule: '规则计划（后端）',
  frontend_mock: '前端模拟计划',
};

export const PLAN_STATUS_LABEL: Record<PlanStatus, string> = {
  proposed: '待确认',
  executed: '已执行',
  expired: '已过期',
  invalidated: '已失效',
};

export const ACTIVITY_SOURCE_LABEL: Record<ActivitySource, string> = {
  user: '用户',
  rule_engine: '规则引擎',
  executor: '执行器',
  virtual_device: '虚拟设备',
  system: '系统',
  frontend_mock: '前端模拟',
};

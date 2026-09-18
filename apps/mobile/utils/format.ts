import type { ActivityKind, ActivitySource, PlanSource, PlanStatus } from '../services/types';

export function formatTime(iso: string): string {
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

export const PLAN_SOURCE_LABEL: Record<PlanSource, string> = {
  rule: '规则计划（后端）',
  model: '模型计划',
  rule_fallback: '规则降级',
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
  experience_agent: 'Experience Agent',
  executor: '执行器',
  virtual_device: '虚拟设备',
  system: '系统',
  simulated_event: '模拟事件',
  simulated_clock: '模拟时钟',
  frontend_mock: '前端模拟',
};

export const ACTIVITY_KIND_LABEL: Record<ActivityKind, string> = {
  plan_created: '生成计划',
  plan_fallback: '规则降级',
  event_received: '收到事件',
  event_ignored: '事件忽略',
  service_adjusted: '自动调整',
  plan_confirmed: '确认执行',
  plan_confirm_repeated: '重复确认',
  plan_rejected: '计划被拒绝',
  action_executed: '设备动作',
  action_rejected: '动作未执行',
  service_stopped: '停止服务',
  memory_updated: '偏好更新',
  energy_mode_changed: '节能设置',
  demo_reset: '重置演示',
  clock_advanced: '模拟时钟',
  schedule_step_executed: '整晚步骤',
  schedule_cancelled: '步骤取消',
  service_completed: '服务完成',
  service_failed: '服务失败',
  clarification_requested: '请求澄清',
  clarification_resolved: '继续请求',
  clarification_cancelled: '取消请求',
};

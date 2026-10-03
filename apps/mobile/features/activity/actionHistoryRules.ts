import type { ActionExecution, RequestContext } from '../../services/types';

export function scopedActions(items: ActionExecution[], context: RequestContext): ActionExecution[] {
  return items.filter((item) => item.spaceId === context.spaceId
    && (item.personId == null || item.personId === context.personId)
    && (item.accountId == null || item.accountId === context.accountId));
}

export function actionStatus(item: ActionExecution): string {
  if (item.status === 'unknown') return item.recoveryExhausted ? '结果未知 · 自动核对已暂停' : '结果未知 · 可核对';
  return ({ pending: '等待发送', dispatching: '正在发送', accepted: '设备已受理',
    completed: '已确认完成', failed: '已确认失败', rejected: '已拒绝', cancelled: '已取消' })[item.status];
}

export function mergeReceipt(items: ActionExecution[], receipt: ActionExecution): ActionExecution[] {
  return items.map((item) => {
    if (item.actionId !== receipt.actionId || item.spaceId !== receipt.spaceId || item.personId !== receipt.personId) return item;
    return ['completed', 'failed', 'rejected', 'cancelled'].includes(item.status) ? item : receipt;
  });
}

// Turn raw activity records into short, human timelines per scene.
import type { ActivityRecord } from '../../services/types';
import { formatTime } from '../../utils/format';

export interface TimelineEntry {
  id: string;
  time: string;
  text: string;
}

const stripReadback = (s: string) => s.replace(/（回读[^）]*）/, '');

export function sceneTimeline(sceneId: string, items: ActivityRecord[]): TimelineEntry[] {
  // Activity arrives newest first; timelines read oldest first.
  const ordered = [...items].reverse();
  const adjustmentPlans = new Set(
    ordered.filter((i) => i.kind === 'service_adjusted' && i.planId).map((i) => i.planId as string),
  );
  const out: TimelineEntry[] = [];
  for (const i of ordered) {
    const inAdjustment = i.planId !== null && adjustmentPlans.has(i.planId);
    let text: string | null = null;
    if (sceneId === 'scene-rest') {
      if (i.kind === 'plan_confirmed') text = '确认了休息计划';
      else if (i.kind === 'action_executed' && !inAdjustment) text = stripReadback(i.message);
      else if (i.kind === 'service_stopped') text = '停止了休息服务，设备保持当前状态';
    } else if (sceneId === 'scene-room-temp') {
      if (i.kind === 'event_received') text = i.message.replace('模拟事件：', '模拟事件 · ');
      else if (i.kind === 'service_adjusted') text = i.message.replace(/^自动调整（[^）]*）：/, '自动调整：');
      else if (i.kind === 'event_ignored') text = i.message.replace('事件已忽略：', '没有调整：');
      else if (i.kind === 'action_executed' && inAdjustment) text = stripReadback(i.message);
    }
    if (text) out.push({ id: i.activityId, time: formatTime(i.timestamp).slice(0, 5), text });
  }
  return out;
}

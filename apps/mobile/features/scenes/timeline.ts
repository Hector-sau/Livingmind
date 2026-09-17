// Turn raw activity records into short, human timelines per scene.
import type { ActivityRecord } from '../../services/types';
import { formatTime } from '../../utils/format';

export interface TimelineEntry {
  id: string;
  time: string;
  text: string;
}

const stripReadback = (s: string) => s.replace(/（回读[^）]*）/, '');

type Origin = 'rest' | 'adjust' | 'night' | 'other';

/**
 * Device actions are attributed to the record that started them (confirm, event adjustment,
 * night step). Plan ids are not enough: the backend logs service actions under the rest plan id.
 */
export function sceneTimeline(sceneId: string, items: ActivityRecord[]): TimelineEntry[] {
  // Activity arrives newest first; timelines read oldest first.
  const ordered = [...items].reverse();
  const out: TimelineEntry[] = [];
  let origin: Origin = 'other';
  for (const i of ordered) {
    if (i.kind === 'plan_confirmed') origin = 'rest';
    else if (i.kind === 'service_adjusted') origin = 'adjust';
    else if (i.kind === 'schedule_step_executed') origin = 'night';
    else if (i.kind !== 'action_executed' && i.kind !== 'action_rejected') origin = 'other';

    let text: string | null = null;
    if (sceneId === 'scene-rest') {
      if (i.kind === 'plan_confirmed') text = '确认了休息计划';
      else if (i.kind === 'action_executed' && origin === 'rest') text = stripReadback(i.message);
      else if (i.kind === 'service_stopped') text = '停止了休息服务，设备保持当前状态';
    } else if (sceneId === 'scene-room-temp') {
      if (i.kind === 'event_received') text = i.message.replace('模拟事件：', '模拟事件 · ');
      else if (i.kind === 'service_adjusted') text = i.message.replace(/^自动调整（[^）]*）：/, '自动调整：');
      else if (i.kind === 'event_ignored') text = i.message.replace('事件已忽略：', '没有调整：');
      else if (i.kind === 'action_executed' && origin === 'adjust') text = stripReadback(i.message);
    } else if (sceneId === 'scene-wake') {
      if (i.kind === 'schedule_step_executed') text = i.message.replace(/^整晚安排 /, '模拟时间 ');
      else if (i.kind === 'service_completed') text = i.message;
      else if (i.kind === 'schedule_cancelled') text = i.message;
    }
    if (text) out.push({ id: i.activityId, time: formatTime(i.timestamp).slice(0, 5), text });
  }
  return out;
}

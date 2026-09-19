// Conversation state for the chat home. Pure and in-memory: nothing is persisted.
import type { ActionResult, AgentStep, DeviceState, Plan } from '../../services/types';

export type Message =
  // `badge` names where the text came from when it was not typed: a tapped example or
  // the keyboard inside the voice sheet. Text a real recogniser produced carries none.
  | { kind: 'user'; id: string; text: string; at: string; badge?: string | null }
  | { kind: 'assistant'; id: string; text: string; trace: AgentStep[]; at: string }
  | { kind: 'plan'; id: string; plan: Plan; at: string }
  | { kind: 'result'; id: string; plan: Plan; results: ActionResult[]; deviceState: DeviceState; repeated: boolean; at: string }
  | { kind: 'system'; id: string; text: string; tone: 'info' | 'success' | 'warning' | 'error'; at: string };

export type Conversations = Record<string, Message[]>;

export type ConversationAction =
  | { type: 'append'; personId: string; message: Message }
  | { type: 'clearAll' };

export function conversationReducer(state: Conversations, action: ConversationAction): Conversations {
  switch (action.type) {
    case 'append': {
      const list = state[action.personId] ?? [];
      return { ...state, [action.personId]: [...list, action.message] };
    }
    case 'clearAll':
      return {};
  }
}

let seq = 0;
export function messageId(): string {
  seq += 1;
  return `m${Date.now().toString(36)}${seq}`;
}

/**
 * Which plan card is still actionable: only the most recent plan message, and only if it is the
 * plan the flow currently holds. Older cards are shown as history.
 */
export function actionablePlanId(messages: Message[], currentPlanId: string | null): string | null {
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    const m = messages[i];
    if (m.kind === 'plan') return m.plan.planId === currentPlanId ? m.plan.planId : null;
  }
  return null;
}

/** One-line human summary of an executed plan. */
export function resultSummary(results: ActionResult[]): string {
  const ok = results.filter((r) => r.outcome === 'succeeded').length;
  if (results.length === 0) return '没有需要执行的动作';
  if (ok === results.length) return `已完成 ${ok} 项设备调整`;
  return `完成 ${ok}/${results.length} 项，其余未执行`;
}

export function greeting(name: string, isGuest: boolean): string {
  return isGuest
    ? '你好。现在是访客模式，我会按这个房间的默认设置来安排，不会读取任何人的个人偏好。想休息的话，直接告诉我。'
    : `你好，${name}。告诉我你现在想怎么休息，我会先给出计划，你确认后才会执行。`;
}

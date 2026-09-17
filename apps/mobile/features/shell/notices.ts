// Timing rules for the top notice bar. Pure, so it can be unit-tested.

export const INFO_DISMISS_MS = 3000;

export type NoticeKind = 'info' | 'warning' | 'error';

/**
 * How long a notice stays before fading out on its own.
 * Info fades after 3 s; warnings and errors stay until the user dismisses them
 * (they carry actions such as "重新读取").
 */
export function autoDismissDelay(kind: NoticeKind | null): number | null {
  return kind === 'info' ? INFO_DISMISS_MS : null;
}

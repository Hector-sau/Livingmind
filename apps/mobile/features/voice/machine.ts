// Voice capture state machine. Pure: no React, no native modules, so it unit-tests
// directly and the same transitions run whether the transcript comes from a tapped
// example, the keyboard, or a real on-device recogniser.
//
// The machine owns capture only. Executing a plan, the undo window and the device
// writes live in the rest flow — mixing them in here is what turns a state machine
// into a god object.

/** Where a transcript came from. Never inferred: the producer states it. */
export type TranscriptSource = 'example' | 'manual' | 'device-asr';

export type VoiceStatus =
  /** Nothing running. */
  | 'idle'
  /** Pressed, but capture has not started yet — exists only so the press feels instant. */
  | 'armed'
  /** Microphone is capturing. Levels are real audio data. */
  | 'listening'
  /** Capture stopped; waiting for a transcript from whichever source is active. */
  | 'resolving'
  /** Transcript handed to the assistant; waiting for its reply. */
  | 'sending'
  /** Text-to-speech is playing. Always interruptible. */
  | 'speaking'
  /** Something went wrong or timed out. Never executes anything. */
  | 'failed';

export type VoiceErrorKind =
  | 'no_speech'
  | 'too_long'
  | 'resolve_timeout'
  | 'send_timeout'
  | 'send_failed'
  | 'permission'
  | 'unavailable';

export const ARM_MS = 200;
export const SILENCE_MS = 1500;
export const MAX_LISTEN_MS = 15_000;
export const NO_SPEECH_MS = 6_000;
export const RESOLVE_TIMEOUT_MS = 20_000;
export const SEND_TIMEOUT_MS = 12_000;

/** Levels at or below this count as silence. Levels are normalised to 0..1 by the source. */
export const SPEECH_LEVEL = 0.08;

/** How many level samples the waveform keeps. */
export const LEVEL_WINDOW = 34;

export interface VoiceMachine {
  readonly status: VoiceStatus;
  /** Timestamp of the last status change. */
  readonly since: number;
  /** Latest normalised level, 0..1. Zero unless capturing. */
  readonly level: number;
  /** Newest-last rolling buffer for the waveform. Empty unless capture has produced levels. */
  readonly levels: readonly number[];
  /** Last time a level crossed SPEECH_LEVEL, or null if no speech has been heard yet. */
  readonly lastVoiceAt: number | null;
  /** Timestamp capture started, for the elapsed-time readout. */
  readonly captureStartedAt: number | null;
  readonly transcript: string | null;
  readonly source: TranscriptSource | null;
  readonly error: VoiceErrorKind | null;
}

export type VoiceEvent =
  | { type: 'press'; at: number }
  | { type: 'level'; value: number; at: number }
  | { type: 'release'; at: number }
  | { type: 'transcript'; text: string; source: TranscriptSource; at: number }
  | { type: 'reply'; ok: boolean; speak: boolean; at: number }
  | { type: 'speech-done'; at: number }
  | { type: 'cancel'; at: number }
  | { type: 'error'; kind: VoiceErrorKind; at: number }
  | { type: 'tick'; at: number };

export const initialVoice: VoiceMachine = {
  status: 'idle',
  since: 0,
  level: 0,
  levels: [],
  lastVoiceAt: null,
  captureStartedAt: null,
  transcript: null,
  source: null,
  error: null,
};

function to(state: VoiceMachine, status: VoiceStatus, at: number, patch: Partial<VoiceMachine> = {}): VoiceMachine {
  return { ...state, ...patch, status, since: at };
}

function reset(at: number, patch: Partial<VoiceMachine> = {}): VoiceMachine {
  return { ...initialVoice, since: at, ...patch };
}

/** Capture is over; wait for the active source to produce (or refuse) a transcript. */
function stopCapture(state: VoiceMachine, at: number): VoiceMachine {
  return to(state, 'resolving', at, { level: 0 });
}

/**
 * The only way the machine changes. Every timeout below lands in `idle` or `failed`;
 * no timeout ever reaches `sending`, so a request that stalls can never turn into a
 * device action on its own.
 */
export function reduceVoice(state: VoiceMachine, event: VoiceEvent): VoiceMachine {
  switch (event.type) {
    case 'press':
      if (state.status !== 'idle' && state.status !== 'failed' && state.status !== 'speaking') return state;
      // Pressing during playback is a barge-in: stop speaking and start over.
      return reset(event.at, { status: 'armed' });

    case 'level': {
      if (state.status !== 'listening') return state;
      const value = clamp01(event.value);
      const levels = [...state.levels, value].slice(-LEVEL_WINDOW);
      return {
        ...state,
        level: value,
        levels,
        lastVoiceAt: value > SPEECH_LEVEL ? event.at : state.lastVoiceAt,
      };
    }

    case 'release':
      if (state.status === 'armed') return reset(event.at);
      if (state.status !== 'listening') return state;
      return stopCapture(state, event.at);

    case 'transcript': {
      // A transcript only counts while the machine is waiting for one. A late result
      // arriving after a cancel must not resurrect the turn.
      if (state.status !== 'resolving' && state.status !== 'listening') return state;
      const text = event.text.trim();
      if (!text) return to(state, 'failed', event.at, { error: 'no_speech', level: 0 });
      return to(state, 'sending', event.at, { transcript: text, source: event.source, level: 0 });
    }

    case 'reply':
      if (state.status !== 'sending') return state;
      if (!event.ok) return to(state, 'failed', event.at, { error: 'send_failed' });
      return event.speak ? to(state, 'speaking', event.at) : reset(event.at);

    case 'speech-done':
      if (state.status !== 'speaking') return state;
      return reset(event.at);

    case 'cancel':
      return reset(event.at);

    case 'error':
      return to(state, 'failed', event.at, { error: event.kind, level: 0 });

    case 'tick':
      return tick(state, event.at);

    default:
      return state;
  }
}

function tick(state: VoiceMachine, at: number): VoiceMachine {
  switch (state.status) {
    case 'armed':
      return at - state.since >= ARM_MS
        ? to(state, 'listening', at, { captureStartedAt: at, lastVoiceAt: null, levels: [] })
        : state;

    case 'listening': {
      const started = state.captureStartedAt ?? state.since;
      if (at - started >= MAX_LISTEN_MS) return to(state, 'failed', at, { error: 'too_long', level: 0 });
      if (state.lastVoiceAt === null) {
        return at - started >= NO_SPEECH_MS ? to(state, 'failed', at, { error: 'no_speech', level: 0 }) : state;
      }
      return at - state.lastVoiceAt >= SILENCE_MS ? stopCapture(state, at) : state;
    }

    case 'resolving':
      return at - state.since >= RESOLVE_TIMEOUT_MS ? to(state, 'failed', at, { error: 'resolve_timeout' }) : state;

    case 'sending':
      return at - state.since >= SEND_TIMEOUT_MS ? to(state, 'failed', at, { error: 'send_timeout' }) : state;

    default:
      return state;
  }
}

function clamp01(value: number): number {
  if (!Number.isFinite(value)) return 0;
  return value < 0 ? 0 : value > 1 ? 1 : value;
}

/** Elapsed capture time in ms, for the "0:03" readout. */
export function captureElapsed(state: VoiceMachine, now: number): number {
  if (state.captureStartedAt === null) return 0;
  if (state.status !== 'listening') return 0;
  return Math.max(0, now - state.captureStartedAt);
}

/** True while the sheet should be on screen. */
export function sheetVisible(state: VoiceMachine): boolean {
  return state.status !== 'idle';
}

/**
 * Every user-visible string for a voice status, in one table.
 *
 * `claimsRecognition` marks the lines that would assert speech recognition. They are
 * only allowed when a real recogniser is attached — `asrConnected` is what flips them,
 * so "did we say something untrue" is one grep, not an audit of every component.
 */
export function statusLabel(status: VoiceStatus, asrConnected: boolean): string {
  switch (status) {
    case 'armed':
    case 'listening':
      return '正在听…';
    case 'resolving':
      return asrConnected ? '正在识别…' : '选一条指令，或直接打字';
    case 'sending':
      return '正在处理…';
    case 'speaking':
      return '正在播报';
    case 'failed':
      return '这次没处理完';
    default:
      return '';
  }
}

export function errorMessage(kind: VoiceErrorKind | null): string {
  switch (kind) {
    case 'no_speech':
      return '没有听到声音。';
    case 'too_long':
      return '这次先听到这里。';
    case 'resolve_timeout':
      return '等太久了，没有执行任何动作。';
    case 'send_timeout':
    case 'send_failed':
      return '没有拿到结果，没有执行任何动作。';
    case 'permission':
      return '没有麦克风权限。';
    case 'unavailable':
      return '这台设备上没有可用的语音识别。';
    default:
      return '';
  }
}

/**
 * Whether the transcript shown to the user needs a source badge.
 * Only a real recogniser produces text the user actually spoke.
 */
export function needsSourceBadge(source: TranscriptSource | null): boolean {
  return source === 'example' || source === 'manual';
}

export function sourceLabel(source: TranscriptSource | null): string {
  switch (source) {
    case 'example':
      return '示例指令';
    case 'manual':
      return '手动输入';
    case 'device-asr':
      return '语音';
    default:
      return '';
  }
}

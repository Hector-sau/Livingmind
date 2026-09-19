// Text-to-speech. This half is genuinely real: expo-speech drives the platform's own
// synthesiser, so "正在播报" and "可随时打断" are honest claims even while the transcript
// beside them may have come from a tapped example.

/** Android caps a single utterance; long text is cut rather than silently dropped. */
export const MAX_SPEECH_CHARS = 380;

/**
 * Trim to something the synthesiser will accept, breaking at a sentence end when one is
 * near the limit so the cut does not land mid-word.
 */
export function truncateForSpeech(text: string, max: number = MAX_SPEECH_CHARS): string {
  const clean = text.replace(/\s+/g, ' ').trim();
  if (clean.length <= max) return clean;
  const head = clean.slice(0, max);
  const lastStop = Math.max(head.lastIndexOf('。'), head.lastIndexOf('；'), head.lastIndexOf('，'), head.lastIndexOf('.'));
  return lastStop > max * 0.6 ? head.slice(0, lastStop + 1) : head;
}

export interface SpeakHandlers {
  onDone(): void;
  /** Fired when stop() cut the utterance short. */
  onStopped(): void;
  onError(): void;
}

export interface Speaker {
  readonly available: boolean;
  speak(text: string, handlers: SpeakHandlers): void;
  /** Interrupts whatever is playing and clears the queue. */
  stop(): void;
}

interface SpeechModule {
  speak(text: string, options: Record<string, unknown>): void;
  stop(): Promise<void>;
}

let cached: SpeechModule | null | undefined;

function loadSpeech(): SpeechModule | null {
  if (cached !== undefined) return cached;
  try {
    // Lazy: absent in plain Node (the unit tests) and harmless to be missing.
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    cached = require('expo-speech') as SpeechModule;
  } catch {
    cached = null;
  }
  return cached;
}

/** Test seam. */
export function resetSpeech(next?: SpeechModule | null): void {
  cached = next;
}

export const SPEECH_LANGUAGE = 'zh-CN';

export function createSpeaker(): Speaker {
  const mod = loadSpeech();
  return {
    available: mod !== null,
    speak(text, handlers) {
      if (!mod) {
        handlers.onDone();
        return;
      }
      // speak() QUEUES rather than interrupts, so a new utterance must stop the old one
      // first or the two play back to back. This is the most common trap in this API.
      void mod.stop();
      const body = truncateForSpeech(text);
      if (!body) {
        handlers.onDone();
        return;
      }
      try {
        mod.speak(body, {
          language: SPEECH_LANGUAGE,
          onDone: handlers.onDone,
          onStopped: handlers.onStopped,
          onError: handlers.onError,
        });
      } catch {
        handlers.onError();
      }
    },
    stop() {
      if (!mod) return;
      try {
        void mod.stop();
      } catch {
        // Nothing playing.
      }
    },
  };
}

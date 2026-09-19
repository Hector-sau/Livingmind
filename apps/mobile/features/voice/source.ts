// The seam between "where spoken words come from" and the rest of the app.
//
// Only a real recogniser implements VoiceSource. Tapping an example or typing does
// NOT go through here — that text never passed through a microphone, and giving it
// the same shape as a recogniser is exactly the confusion this project must avoid.
// The rest flow calls `submit(text, 'example' | 'manual')` directly for those.

import type { VoiceErrorKind } from './machine';

export interface VoiceSourceHandlers {
  /** Normalised 0..1 microphone level. Real audio data, or the source must not call this. */
  onLevel(value: number): void;
  /** A final transcript. Interim results are not forwarded: half a sentence is not a request. */
  onTranscript(text: string): void;
  /** The recogniser decided the utterance is over without producing text. */
  onNoMatch(): void;
  onError(kind: VoiceErrorKind, detail: string): void;
}

export interface VoiceCapture {
  /** Ask for a final result and stop. Safe to call more than once. */
  stop(): void;
  /** Drop the capture with no result. Safe to call more than once. */
  abort(): void;
}

export type VoiceAvailability =
  | { ok: true; onDevice: boolean }
  | { ok: false; reason: VoiceErrorKind; detail: string };

export interface VoiceSource {
  /** Whether this source can run right now, on this device, with permission granted. */
  available(): Promise<VoiceAvailability>;
  start(handlers: VoiceSourceHandlers): Promise<VoiceCapture>;
}

/**
 * Stand-in for builds with no recogniser: web, Expo Go, or a device whose platform
 * has none. Reports itself unavailable rather than pretending to listen.
 */
export const unavailableSource: VoiceSource = {
  async available() {
    return { ok: false, reason: 'unavailable', detail: '这个版本没有编入语音识别' };
  },
  async start() {
    throw new Error('voice source unavailable');
  },
};

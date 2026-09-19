// On-device speech recognition, via the platform's own recogniser
// (SFSpeechRecognizer on iOS, SpeechRecognizer on Android). No API key, no cloud
// service, no cost — and with `requiresOnDeviceRecognition` the audio never leaves
// the device.
//
// NOT VERIFIED ON HARDWARE. This needs a development build (the native module is not
// in Expo Go) and a real device with a microphone. Neither the cloud workspace nor the
// browser end-to-end suite can execute this path, so nothing here may be described as
// working until someone runs it on a tablet. Everything below is written so that a
// failure degrades to the text path instead of breaking the screen.

import type { VoiceErrorKind } from './machine';
import type { VoiceAvailability, VoiceCapture, VoiceSource, VoiceSourceHandlers } from './source';

/** Volume events report -2..10, where anything below 0 is inaudible. */
export function normaliseLevel(raw: number): number {
  if (!Number.isFinite(raw)) return 0;
  if (raw <= 0) return 0;
  const scaled = raw / 10;
  return scaled > 1 ? 1 : scaled;
}

/** Map the recogniser's error codes onto the machine's, so the UI has one vocabulary. */
export function mapError(code: string): VoiceErrorKind {
  switch (code) {
    case 'not-allowed':
      return 'permission';
    case 'no-speech':
    case 'speech-timeout':
      return 'no_speech';
    case 'service-not-allowed':
    case 'language-not-supported':
    case 'bad-grammar':
      return 'unavailable';
    default:
      // audio-capture, network, busy, client, interrupted, unknown — all "we got nothing".
      return 'resolve_timeout';
  }
}

/** The subset of the native module this adapter uses. Keeps the import lazy and typed. */
interface SpeechModule {
  start(options: Record<string, unknown>): void;
  stop(): void;
  abort(): void;
  isRecognitionAvailable(): boolean;
  supportsOnDeviceRecognition(): boolean;
  getPermissionsAsync(): Promise<{ granted: boolean; canAskAgain: boolean }>;
  requestPermissionsAsync(): Promise<{ granted: boolean; canAskAgain: boolean }>;
  addListener(event: string, listener: (payload: never) => void): { remove(): void };
}

let cached: SpeechModule | null | undefined;

/**
 * Load the native module without letting its absence take the app down. It is missing
 * on web and in Expo Go, and that is a supported state, not an error.
 */
export function loadSpeechModule(): SpeechModule | null {
  if (cached !== undefined) return cached;
  try {
    // Both requires are lazy: react-native and the native module are absent in plain
    // Node (the unit tests) and the module is absent on web and in Expo Go. Neither
    // is an error — they mean "no recogniser here".
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const { Platform } = require('react-native') as { Platform: { OS: string } };
    if (Platform.OS === 'web') {
      cached = null;
      return cached;
    }
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const mod = require('expo-speech-recognition') as { ExpoSpeechRecognitionModule?: SpeechModule };
    cached = mod?.ExpoSpeechRecognitionModule ?? null;
  } catch {
    cached = null;
  }
  return cached;
}

/** Test seam: drop the memoised module so a fake can be installed. */
export function resetSpeechModule(next?: SpeechModule | null): void {
  cached = next;
}

export const DEVICE_LOCALE = 'zh-CN';

export function createDeviceSpeechSource(): VoiceSource {
  return {
    async available(): Promise<VoiceAvailability> {
      const mod = loadSpeechModule();
      if (!mod) return { ok: false, reason: 'unavailable', detail: '这个版本没有编入语音识别' };

      let usable = false;
      try {
        usable = mod.isRecognitionAvailable();
      } catch {
        return { ok: false, reason: 'unavailable', detail: '识别服务不可用' };
      }
      if (!usable) return { ok: false, reason: 'unavailable', detail: '这台设备上没有可用的识别服务' };

      let granted = false;
      try {
        granted = (await mod.getPermissionsAsync()).granted;
        if (!granted) granted = (await mod.requestPermissionsAsync()).granted;
      } catch {
        granted = false;
      }
      if (!granted) return { ok: false, reason: 'permission', detail: '没有麦克风或语音识别权限' };

      let onDevice = false;
      try {
        onDevice = mod.supportsOnDeviceRecognition();
      } catch {
        onDevice = false;
      }
      return { ok: true, onDevice };
    },

    async start(handlers: VoiceSourceHandlers): Promise<VoiceCapture> {
      const mod = loadSpeechModule();
      if (!mod) throw new Error('speech recognition module is not installed');

      let onDevice = false;
      try {
        onDevice = mod.supportsOnDeviceRecognition();
      } catch {
        onDevice = false;
      }

      let finished = false;
      const subscriptions: { remove(): void }[] = [];
      const cleanup = () => {
        if (finished) return;
        finished = true;
        for (const sub of subscriptions) {
          try {
            sub.remove();
          } catch {
            // A listener that is already gone is not a problem.
          }
        }
      };

      const listen = (event: string, listener: (payload: never) => void) => {
        try {
          subscriptions.push(mod.addListener(event, listener));
        } catch {
          // An event this platform does not emit simply never fires.
        }
      };

      listen('volumechange', ((payload: { value: number }) => {
        if (finished) return;
        handlers.onLevel(normaliseLevel(payload?.value ?? 0));
      }) as never);

      listen('result', ((payload: { isFinal: boolean; results?: { transcript?: string }[] }) => {
        if (finished) return;
        // Interim results are deliberately dropped: only a final transcript is a request.
        if (!payload?.isFinal) return;
        const text = payload.results?.[0]?.transcript ?? '';
        cleanup();
        if (text.trim()) handlers.onTranscript(text);
        else handlers.onNoMatch();
      }) as never);

      listen('nomatch', (() => {
        if (finished) return;
        cleanup();
        handlers.onNoMatch();
      }) as never);

      listen('error', ((payload: { error: string; message?: string }) => {
        if (finished) return;
        // `abort()` reports itself as an error; the caller already knows it cancelled.
        if (payload?.error === 'aborted') {
          cleanup();
          return;
        }
        cleanup();
        handlers.onError(mapError(payload?.error ?? 'unknown'), payload?.message ?? '');
      }) as never);

      try {
        mod.start({
          lang: DEVICE_LOCALE,
          interimResults: false,
          continuous: false,
          requiresOnDeviceRecognition: onDevice,
          volumeChangeEventOptions: { enabled: true, intervalMillis: 100 },
        });
      } catch (err) {
        cleanup();
        throw err instanceof Error ? err : new Error('failed to start speech recognition');
      }

      return {
        stop() {
          try {
            mod.stop();
          } catch {
            cleanup();
          }
        },
        abort() {
          cleanup();
          try {
            mod.abort();
          } catch {
            // Already stopped.
          }
        },
      };
    },
  };
}

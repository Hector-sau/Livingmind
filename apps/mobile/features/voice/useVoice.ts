import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { createDeviceSpeechSource } from './deviceSpeech';
import {
  initialVoice,
  reduceVoice,
  type TranscriptSource,
  type VoiceEvent,
  type VoiceMachine,
} from './machine';
import type { VoiceCapture, VoiceSource } from './source';
import { createSpeaker } from './speech';

/** How often the machine is nudged so its timeouts fire. */
const TICK_MS = 200;

export interface VoiceController {
  state: VoiceMachine;
  /** True once a real recogniser has been found and permitted on this device. */
  asrConnected: boolean;
  /** Start a capture (or interrupt playback and start a new one). */
  press(): void;
  /** Finish a capture and ask for a result. */
  release(): void;
  /** Hand the machine a transcript from a tapped example or the keyboard. */
  submit(text: string, source: TranscriptSource): void;
  cancel(): void;
  /** Report how the assistant's reply went, and optionally speak it. */
  settle(ok: boolean, spokenText: string | null): void;
  /** Stop playback immediately. */
  skipSpeech(): void;
}

interface Options {
  /** Injectable for tests; defaults to the on-device recogniser. */
  source?: VoiceSource;
  enabled?: boolean;
}

/**
 * Owns the voice machine and the two pieces of the outside world it talks to: the
 * recogniser (if this build has one) and the synthesiser.
 *
 * The machine stays pure; everything with a side effect is here, so the transitions
 * remain testable without a device.
 */
export function useVoice(options: Options = {}): VoiceController {
  const [state, setState] = useState<VoiceMachine>(initialVoice);
  const [asrConnected, setAsrConnected] = useState(false);
  const captureRef = useRef<VoiceCapture | null>(null);
  const stateRef = useRef(state);
  stateRef.current = state;

  const source = useMemo(() => options.source ?? createDeviceSpeechSource(), [options.source]);
  const speaker = useMemo(() => createSpeaker(), []);

  const dispatch = useCallback((event: VoiceEvent) => {
    setState((s) => reduceVoice(s, event));
  }, []);

  // Probe once: a build without the native module, a device without a recogniser and a
  // refused permission all land in the same place — no recogniser, text path only.
  useEffect(() => {
    let cancelled = false;
    void source.available().then((result) => {
      if (!cancelled) setAsrConnected(result.ok);
    });
    return () => {
      cancelled = true;
    };
  }, [source]);

  // One timer drives every timeout in the machine.
  useEffect(() => {
    if (state.status === 'idle') return;
    const timer = setInterval(() => dispatch({ type: 'tick', at: Date.now() }), TICK_MS);
    return () => clearInterval(timer);
  }, [state.status, dispatch]);

  const stopCapture = useCallback((abort: boolean) => {
    const capture = captureRef.current;
    captureRef.current = null;
    if (!capture) return;
    if (abort) capture.abort();
    else capture.stop();
  }, []);

  const press = useCallback(() => {
    speaker.stop();
    dispatch({ type: 'press', at: Date.now() });
    if (!asrConnected) return;
    void source
      .start({
        onLevel: (value) => dispatch({ type: 'level', value, at: Date.now() }),
        onTranscript: (text) => {
          captureRef.current = null;
          dispatch({ type: 'transcript', text, source: 'device-asr', at: Date.now() });
        },
        onNoMatch: () => {
          captureRef.current = null;
          dispatch({ type: 'error', kind: 'no_speech', at: Date.now() });
        },
        onError: (kind) => {
          captureRef.current = null;
          dispatch({ type: 'error', kind, at: Date.now() });
        },
      })
      .then((capture) => {
        captureRef.current = capture;
      })
      .catch(() => dispatch({ type: 'error', kind: 'unavailable', at: Date.now() }));
  }, [asrConnected, dispatch, source, speaker]);

  const release = useCallback(() => {
    stopCapture(false);
    dispatch({ type: 'release', at: Date.now() });
  }, [dispatch, stopCapture]);

  const submit = useCallback(
    (text: string, transcriptSource: TranscriptSource) => {
      stopCapture(true);
      dispatch({ type: 'transcript', text, source: transcriptSource, at: Date.now() });
    },
    [dispatch, stopCapture],
  );

  const cancel = useCallback(() => {
    stopCapture(true);
    speaker.stop();
    dispatch({ type: 'cancel', at: Date.now() });
  }, [dispatch, speaker, stopCapture]);

  const settle = useCallback(
    (ok: boolean, spokenText: string | null) => {
      const speak = ok && !!spokenText && speaker.available;
      dispatch({ type: 'reply', ok, speak, at: Date.now() });
      if (!speak || !spokenText) return;
      speaker.speak(spokenText, {
        onDone: () => dispatch({ type: 'speech-done', at: Date.now() }),
        onStopped: () => dispatch({ type: 'speech-done', at: Date.now() }),
        onError: () => dispatch({ type: 'speech-done', at: Date.now() }),
      });
    },
    [dispatch, speaker],
  );

  const skipSpeech = useCallback(() => {
    speaker.stop();
    dispatch({ type: 'speech-done', at: Date.now() });
  }, [dispatch, speaker]);

  // Never leave a microphone open behind a closing screen.
  useEffect(
    () => () => {
      captureRef.current?.abort();
      captureRef.current = null;
      speaker.stop();
    },
    [speaker],
  );

  return { state, asrConnected, press, release, submit, cancel, settle, skipSpeech };
}

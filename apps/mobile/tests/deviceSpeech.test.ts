import assert from 'node:assert/strict';
import { test } from 'node:test';

import {
  createDeviceSpeechSource,
  loadSpeechModule,
  mapError,
  normaliseLevel,
  resetSpeechModule,
} from '../features/voice/deviceSpeech';

/** A stand-in for the native module, so the adapter's wiring is testable off-device. */
function fakeModule(overrides: Record<string, unknown> = {}) {
  const listeners = new Map<string, (payload: unknown) => void>();
  const calls: string[] = [];
  const mod = {
    started: null as Record<string, unknown> | null,
    listeners,
    calls,
    removed: 0,
    start(options: Record<string, unknown>) {
      calls.push('start');
      mod.started = options;
    },
    stop() {
      calls.push('stop');
    },
    abort() {
      calls.push('abort');
    },
    isRecognitionAvailable: () => true,
    supportsOnDeviceRecognition: () => true,
    getPermissionsAsync: async () => ({ granted: true, canAskAgain: true }),
    requestPermissionsAsync: async () => ({ granted: true, canAskAgain: true }),
    addListener(event: string, listener: (payload: never) => void) {
      listeners.set(event, listener as (payload: unknown) => void);
      return {
        remove() {
          mod.removed += 1;
          listeners.delete(event);
        },
      };
    },
    emit(event: string, payload: unknown) {
      listeners.get(event)?.(payload);
    },
    ...overrides,
  };
  return mod;
}

function handlers() {
  const seen = { levels: [] as number[], transcripts: [] as string[], noMatch: 0, errors: [] as string[] };
  return {
    seen,
    onLevel: (v: number) => seen.levels.push(v),
    onTranscript: (t: string) => seen.transcripts.push(t),
    onNoMatch: () => {
      seen.noMatch += 1;
    },
    onError: (kind: string) => seen.errors.push(kind),
  };
}

test('volume values map onto 0..1, with everything inaudible pinned to zero', () => {
  assert.equal(normaliseLevel(-2), 0);
  assert.equal(normaliseLevel(0), 0);
  assert.equal(normaliseLevel(5), 0.5);
  assert.equal(normaliseLevel(10), 1);
  assert.equal(normaliseLevel(99), 1, 'out-of-range values are clamped, not trusted');
  assert.equal(normaliseLevel(Number.NaN), 0);
});

test('recogniser error codes collapse into the vocabulary the UI already speaks', () => {
  assert.equal(mapError('not-allowed'), 'permission');
  assert.equal(mapError('no-speech'), 'no_speech');
  assert.equal(mapError('speech-timeout'), 'no_speech');
  assert.equal(mapError('service-not-allowed'), 'unavailable');
  assert.equal(mapError('language-not-supported'), 'unavailable');
  assert.equal(mapError('network'), 'resolve_timeout');
  assert.equal(mapError('something-new'), 'resolve_timeout', 'unknown codes must still be handled');
});

test('a missing native module is reported as unavailable, never as a crash', async () => {
  resetSpeechModule(null);
  assert.equal(loadSpeechModule(), null);
  const result = await createDeviceSpeechSource().available();
  assert.equal(result.ok, false);
  assert.equal(result.ok === false && result.reason, 'unavailable');
  resetSpeechModule(undefined);
});

test('a refused permission is reported as such, not as a broken device', async () => {
  resetSpeechModule(
    fakeModule({
      getPermissionsAsync: async () => ({ granted: false, canAskAgain: true }),
      requestPermissionsAsync: async () => ({ granted: false, canAskAgain: false }),
    }) as never,
  );
  const result = await createDeviceSpeechSource().available();
  assert.equal(result.ok, false);
  assert.equal(result.ok === false && result.reason, 'permission');
  resetSpeechModule(undefined);
});

test('a device with no recogniser is unavailable even when permission is granted', async () => {
  resetSpeechModule(fakeModule({ isRecognitionAvailable: () => false }) as never);
  const result = await createDeviceSpeechSource().available();
  assert.equal(result.ok, false);
  assert.equal(result.ok === false && result.reason, 'unavailable');
  resetSpeechModule(undefined);
});

test('capture asks for on-device recognition and real volume events', async () => {
  const mod = fakeModule();
  resetSpeechModule(mod as never);
  await createDeviceSpeechSource().start(handlers());
  assert.equal(mod.started?.requiresOnDeviceRecognition, true, 'audio should stay on the device when it can');
  assert.equal(mod.started?.interimResults, false, 'half a sentence is not a request');
  assert.equal(mod.started?.lang, 'zh-CN');
  assert.deepEqual(mod.started?.volumeChangeEventOptions, { enabled: true, intervalMillis: 100 });
  resetSpeechModule(undefined);
});

test('only a final transcript is forwarded; interim results are dropped', async () => {
  const mod = fakeModule();
  resetSpeechModule(mod as never);
  const h = handlers();
  await createDeviceSpeechSource().start(h);

  mod.emit('result', { isFinal: false, results: [{ transcript: '把灯' }] });
  assert.deepEqual(h.seen.transcripts, [], 'an interim result must not start a request');

  mod.emit('result', { isFinal: true, results: [{ transcript: '把灯调到 20%' }] });
  assert.deepEqual(h.seen.transcripts, ['把灯调到 20%']);
  resetSpeechModule(undefined);
});

test('a final result with no text is a no-match, not an empty command', async () => {
  const mod = fakeModule();
  resetSpeechModule(mod as never);
  const h = handlers();
  await createDeviceSpeechSource().start(h);
  mod.emit('result', { isFinal: true, results: [{ transcript: '   ' }] });
  assert.deepEqual(h.seen.transcripts, []);
  assert.equal(h.seen.noMatch, 1);
  resetSpeechModule(undefined);
});

test('levels arrive normalised', async () => {
  const mod = fakeModule();
  resetSpeechModule(mod as never);
  const h = handlers();
  await createDeviceSpeechSource().start(h);
  mod.emit('volumechange', { value: 10 });
  mod.emit('volumechange', { value: -1 });
  assert.deepEqual(h.seen.levels, [1, 0]);
  resetSpeechModule(undefined);
});

test('the listeners are torn down once a turn ends, so a late event cannot fire twice', async () => {
  const mod = fakeModule();
  resetSpeechModule(mod as never);
  const h = handlers();
  await createDeviceSpeechSource().start(h);

  mod.emit('result', { isFinal: true, results: [{ transcript: '关灯' }] });
  assert.equal(h.seen.transcripts.length, 1);
  assert.ok(mod.removed > 0, 'subscriptions are removed');

  mod.emit('result', { isFinal: true, results: [{ transcript: '再来一次' }] });
  assert.equal(h.seen.transcripts.length, 1, 'a second result after the turn ended is ignored');
  resetSpeechModule(undefined);
});

test('aborting is silent, but a real error is reported', async () => {
  const aborted = fakeModule();
  resetSpeechModule(aborted as never);
  const h1 = handlers();
  const capture = await createDeviceSpeechSource().start(h1);
  capture.abort();
  aborted.emit('error', { error: 'aborted', message: 'user cancelled' });
  assert.deepEqual(h1.seen.errors, [], 'the user already knows they cancelled');
  assert.ok(aborted.calls.includes('abort'));

  const broken = fakeModule();
  resetSpeechModule(broken as never);
  const h2 = handlers();
  await createDeviceSpeechSource().start(h2);
  broken.emit('error', { error: 'not-allowed', message: 'no permission' });
  assert.deepEqual(h2.seen.errors, ['permission']);
  resetSpeechModule(undefined);
});

test('stop asks for a final result; abort does not', async () => {
  const mod = fakeModule();
  resetSpeechModule(mod as never);
  const capture = await createDeviceSpeechSource().start(handlers());
  capture.stop();
  assert.ok(mod.calls.includes('stop'));
  assert.ok(!mod.calls.includes('abort'));
  resetSpeechModule(undefined);
});

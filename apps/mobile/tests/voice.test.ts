import assert from 'node:assert/strict';
import { test } from 'node:test';

import {
  ARM_MS,
  LEVEL_WINDOW,
  MAX_LISTEN_MS,
  NO_SPEECH_MS,
  RESOLVE_TIMEOUT_MS,
  SEND_TIMEOUT_MS,
  SILENCE_MS,
  captureElapsed,
  errorMessage,
  initialVoice,
  needsSourceBadge,
  reduceVoice,
  sourceLabel,
  statusLabel,
  type VoiceEvent,
  type VoiceMachine,
} from '../features/voice/machine';

function run(events: VoiceEvent[], from: VoiceMachine = initialVoice): VoiceMachine {
  return events.reduce(reduceVoice, from);
}

/** Press, wait out the arm delay, and speak, so tests start from a real capture. */
function listening(at = 0): VoiceMachine {
  return run([
    { type: 'press', at },
    { type: 'tick', at: at + ARM_MS },
    { type: 'level', value: 0.6, at: at + ARM_MS + 10 },
  ]);
}

test('press gives instant feedback before capture starts', () => {
  const armed = run([{ type: 'press', at: 0 }]);
  assert.equal(armed.status, 'armed');
  assert.equal(armed.captureStartedAt, null, 'nothing is captured until the arm delay passes');

  const still = reduceVoice(armed, { type: 'tick', at: ARM_MS - 1 });
  assert.equal(still.status, 'armed');

  const started = reduceVoice(armed, { type: 'tick', at: ARM_MS });
  assert.equal(started.status, 'listening');
  assert.equal(started.captureStartedAt, ARM_MS);
});

test('releasing before capture starts leaves nothing behind', () => {
  const state = run([{ type: 'press', at: 0 }, { type: 'release', at: 50 }]);
  assert.equal(state.status, 'idle');
  assert.equal(state.transcript, null);
});

test('levels only accumulate while listening, and the waveform buffer is bounded', () => {
  let state = listening();
  for (let i = 0; i < LEVEL_WINDOW * 2; i += 1) {
    state = reduceVoice(state, { type: 'level', value: 0.5, at: 1000 + i });
  }
  assert.equal(state.levels.length, LEVEL_WINDOW);

  const idle = reduceVoice(initialVoice, { type: 'level', value: 0.9, at: 10 });
  assert.equal(idle.levels.length, 0, 'a stray level while idle must not draw a waveform');
  assert.equal(idle.level, 0);
});

test('silence after speech ends capture; the level drops to zero', () => {
  const state = listening();
  const spokeAt = state.lastVoiceAt ?? 0;
  const quiet = reduceVoice(state, { type: 'tick', at: spokeAt + SILENCE_MS });
  assert.equal(quiet.status, 'resolving');
  assert.equal(quiet.level, 0, 'the waveform must stop moving once the mic is no longer read');
});

test('never hearing any speech fails instead of waiting forever', () => {
  const armed = run([{ type: 'press', at: 0 }, { type: 'tick', at: ARM_MS }]);
  assert.equal(armed.lastVoiceAt, null);
  const gaveUp = reduceVoice(armed, { type: 'tick', at: ARM_MS + NO_SPEECH_MS });
  assert.equal(gaveUp.status, 'failed');
  assert.equal(gaveUp.error, 'no_speech');
});

test('capture is cut off at the maximum length', () => {
  const state = listening();
  const cut = reduceVoice(state, { type: 'tick', at: (state.captureStartedAt ?? 0) + MAX_LISTEN_MS });
  assert.equal(cut.status, 'failed');
  assert.equal(cut.error, 'too_long');
});

test('a transcript carries its source and moves the turn forward', () => {
  const state = run([{ type: 'release', at: 500 }], listening());
  assert.equal(state.status, 'resolving');

  const sent = reduceVoice(state, { type: 'transcript', text: '  把灯调到 20%  ', source: 'example', at: 600 });
  assert.equal(sent.status, 'sending');
  assert.equal(sent.transcript, '把灯调到 20%', 'the transcript is trimmed');
  assert.equal(sent.source, 'example');
});

test('an empty transcript is a failure, not an empty request', () => {
  const state = run([{ type: 'release', at: 500 }], listening());
  const empty = reduceVoice(state, { type: 'transcript', text: '   ', source: 'device-asr', at: 600 });
  assert.equal(empty.status, 'failed');
  assert.equal(empty.error, 'no_speech');
});

test('a transcript arriving after cancel does not resurrect the turn', () => {
  const cancelled = run([{ type: 'release', at: 500 }, { type: 'cancel', at: 520 }], listening());
  assert.equal(cancelled.status, 'idle');

  const late = reduceVoice(cancelled, { type: 'transcript', text: '关灯', source: 'device-asr', at: 900 });
  assert.equal(late.status, 'idle', 'a late recogniser result must not start a request');
  assert.equal(late.transcript, null);
});

test('every timeout lands somewhere that cannot execute', () => {
  const resolving = run([{ type: 'release', at: 500 }], listening());
  const stalled = reduceVoice(resolving, { type: 'tick', at: 500 + RESOLVE_TIMEOUT_MS });
  assert.equal(stalled.status, 'failed');
  assert.equal(stalled.error, 'resolve_timeout');

  const sending = reduceVoice(resolving, { type: 'transcript', text: '关灯', source: 'manual', at: 600 });
  const lost = reduceVoice(sending, { type: 'tick', at: 600 + SEND_TIMEOUT_MS });
  assert.equal(lost.status, 'failed');
  assert.equal(lost.error, 'send_timeout');

  for (const state of [stalled, lost]) {
    assert.notEqual(state.status, 'sending', 'a timeout must never hand text onward');
  }
});

test('a failed reply is reported; a successful one may speak', () => {
  const sending = run(
    [{ type: 'release', at: 500 }, { type: 'transcript', text: '关灯', source: 'manual', at: 600 }],
    listening(),
  );

  const failed = reduceVoice(sending, { type: 'reply', ok: false, speak: false, at: 700 });
  assert.equal(failed.status, 'failed');
  assert.equal(failed.error, 'send_failed');

  const quiet = reduceVoice(sending, { type: 'reply', ok: true, speak: false, at: 700 });
  assert.equal(quiet.status, 'idle');

  const spoken = reduceVoice(sending, { type: 'reply', ok: true, speak: true, at: 700 });
  assert.equal(spoken.status, 'speaking');
  assert.equal(reduceVoice(spoken, { type: 'speech-done', at: 900 }).status, 'idle');
});

test('pressing during playback interrupts it and starts a new capture', () => {
  const speaking = run(
    [
      { type: 'release', at: 500 },
      { type: 'transcript', text: '关灯', source: 'manual', at: 600 },
      { type: 'reply', ok: true, speak: true, at: 700 },
    ],
    listening(),
  );
  assert.equal(speaking.status, 'speaking');

  const again = reduceVoice(speaking, { type: 'press', at: 800 });
  assert.equal(again.status, 'armed');
  assert.equal(again.transcript, null, 'the new turn starts clean');
});

test('cancel works from every running state', () => {
  const armed = run([{ type: 'press', at: 0 }]);
  const captured = listening();
  const resolving = run([{ type: 'release', at: 500 }], captured);
  const sending = reduceVoice(resolving, { type: 'transcript', text: '关灯', source: 'manual', at: 600 });

  for (const state of [armed, captured, resolving, sending]) {
    assert.equal(reduceVoice(state, { type: 'cancel', at: 9_999 }).status, 'idle');
  }
});

test('elapsed time is only reported while the microphone is open', () => {
  const state = listening(0);
  assert.equal(captureElapsed(state, (state.captureStartedAt ?? 0) + 3_000), 3_000);

  const stopped = reduceVoice(state, { type: 'release', at: 5_000 });
  assert.equal(captureElapsed(stopped, 9_000), 0, 'a stopped capture must not keep counting');
});

test('copy that would claim recognition is gated on a real recogniser', () => {
  assert.equal(statusLabel('resolving', false), '选一条指令，或直接打字');
  assert.equal(statusLabel('resolving', true), '正在识别…');
  for (const connected of [false, true]) {
    assert.ok(!statusLabel('listening', connected).includes('识别'), 'capturing is not recognising');
  }
});

test('simulated transcripts are badged; recognised speech is labelled as voice', () => {
  assert.equal(needsSourceBadge('example'), true);
  assert.equal(needsSourceBadge('manual'), true);
  assert.equal(needsSourceBadge('device-asr'), false);
  assert.equal(sourceLabel('example'), '示例指令');
  assert.equal(sourceLabel('device-asr'), '语音');
});

test('every failure says that nothing was executed, or why', () => {
  for (const kind of ['no_speech', 'too_long', 'resolve_timeout', 'send_timeout', 'send_failed', 'permission', 'unavailable'] as const) {
    assert.ok(errorMessage(kind).length > 0, `${kind} needs a message`);
  }
});

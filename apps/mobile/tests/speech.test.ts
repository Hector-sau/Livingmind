import assert from 'node:assert/strict';
import { test } from 'node:test';

import { MAX_SPEECH_CHARS, createSpeaker, resetSpeech, truncateForSpeech } from '../features/voice/speech';

function fakeSpeech() {
  const calls: { text: string; options: Record<string, unknown> }[] = [];
  let stops = 0;
  return {
    calls,
    get stops() {
      return stops;
    },
    speak(text: string, options: Record<string, unknown>) {
      calls.push({ text, options });
    },
    async stop() {
      stops += 1;
    },
  };
}

test('short text is passed through with whitespace collapsed', () => {
  assert.equal(truncateForSpeech('  灯光已调到 20%。  '), '灯光已调到 20%。');
  assert.equal(truncateForSpeech('两行\n文字'), '两行 文字');
});

test('long text is cut at a sentence end when one is near the limit', () => {
  const sentence = '这是一句用来测试的中文句子。';
  const long = sentence.repeat(40);
  const cut = truncateForSpeech(long);
  assert.ok(cut.length <= MAX_SPEECH_CHARS);
  assert.ok(cut.endsWith('。'), `expected a clean break, got ${cut.slice(-12)}`);
});

test('text with no break point is cut hard rather than dropped', () => {
  const wall = 'あ'.repeat(MAX_SPEECH_CHARS * 2);
  const cut = truncateForSpeech(wall);
  assert.equal(cut.length, MAX_SPEECH_CHARS);
});

test('speaking stops whatever is playing first, because speak() queues', () => {
  const mod = fakeSpeech();
  resetSpeech(mod as never);
  const speaker = createSpeaker();
  const noop = { onDone() {}, onStopped() {}, onError() {} };

  speaker.speak('第一句', noop);
  speaker.speak('第二句', noop);

  assert.equal(mod.calls.length, 2);
  assert.equal(mod.stops, 2, 'each utterance interrupts the previous one instead of queueing behind it');
  assert.equal(mod.calls[1].text, '第二句');
  resetSpeech(undefined);
});

test('the language is set explicitly and the callbacks are wired', () => {
  const mod = fakeSpeech();
  resetSpeech(mod as never);
  let done = 0;
  createSpeaker().speak('好的', { onDone: () => (done += 1), onStopped() {}, onError() {} });

  const options = mod.calls[0].options;
  assert.equal(options.language, 'zh-CN');
  (options.onDone as () => void)();
  assert.equal(done, 1);
  resetSpeech(undefined);
});

test('with no synthesiser the turn still finishes instead of hanging', () => {
  resetSpeech(null);
  const speaker = createSpeaker();
  assert.equal(speaker.available, false);

  let done = 0;
  speaker.speak('没有合成器', { onDone: () => (done += 1), onStopped() {}, onError() {} });
  assert.equal(done, 1, 'onDone must still fire, or the machine would sit in "speaking" forever');
  speaker.stop();
  resetSpeech(undefined);
});

test('empty text completes without calling the synthesiser', () => {
  const mod = fakeSpeech();
  resetSpeech(mod as never);
  let done = 0;
  createSpeaker().speak('   ', { onDone: () => (done += 1), onStopped() {}, onError() {} });
  assert.equal(mod.calls.length, 0);
  assert.equal(done, 1);
  resetSpeech(undefined);
});

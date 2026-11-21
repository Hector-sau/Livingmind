const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const code = readFileSync(join(__dirname, '../apps/family-demo/voice.js'), 'utf8');

function setup(supported = true) {
  const seen = { recorders: [], messages: [], texts: [], speeches: [] };
  class Recognition {
    constructor() { seen.recorders.push(this); }
    start() { this.onstart(); }
    stop() { this.stopped = true; }
    abort() { this.aborted = true; this.onend?.(); }
  }
  const window = supported ? {
    webkitSpeechRecognition: Recognition,
    SpeechSynthesisUtterance: class { constructor(text) { this.text = text; } },
    speechSynthesis: {
      getVoices: () => [{ lang: 'zh-CN' }],
      speak: (utterance) => seen.speeches.push(utterance),
      cancel: () => seen.cancelled = true,
    },
  } : {};
  vm.runInNewContext(code, { window });
  const voice = window.FamilyVoice.create({
    onStatus: (value) => seen.messages.push(value),
    onTranscript: (value) => seen.texts.push(value),
  });
  return { voice, seen };
}

function result(text, final = true) {
  return { results: [Object.assign([{ transcript: text }], { isFinal: final })] };
}

test('unavailable recognizer never generates a transcript; sample is labeled', () => {
  const { voice, seen } = setup(false);
  assert.equal(voice.listen(), false);
  assert.equal(seen.messages.at(-1).phase, 'unavailable');
  assert.equal(seen.texts.length, 0);
  assert.equal(voice.selectMember('adult').verified, false);
  voice.example('我想休息');
  assert.equal(seen.texts[0].source, 'simulated-transcript');
  assert.equal(seen.texts[0].memberId, 'adult');
  assert.equal(voice.speak('你好'), false);
});

test('Chinese interim and final results remain editable, stop waits for final result', () => {
  const { voice, seen } = setup();
  voice.listen();
  voice.listen();
  assert.equal(seen.recorders.length, 1);
  const r = seen.recorders[0];
  assert.equal(r.lang, 'zh-CN');
  r.onresult(result('晚', false));
  voice.stop();
  assert.equal(r.stopped, true);
  r.onresult(result('晚安'));
  r.onend();
  assert.equal(seen.texts[0].final, false);
  assert.equal(seen.texts[1].source, 'browser-asr');
  assert.equal(seen.texts[1].text, '晚安');
  assert.equal(seen.messages.at(-1).phase, 'idle');
});

test('switching resident prevents late results from crossing into the new profile', () => {
  const { voice, seen } = setup();
  voice.selectMember('first');
  voice.listen();
  const previous = seen.recorders[0];
  assert.equal(voice.selectMember('second').identitySource, 'manual-selection');
  previous.onresult(result('旧的消息'));
  assert.equal(previous.aborted, true);
  assert.equal(seen.texts.length, 0);
});

test('permission errors survive end callbacks and the user can retry', () => {
  const { voice, seen } = setup();
  voice.listen();
  seen.recorders[0].onerror({ error: 'not-allowed' });
  seen.recorders[0].onend();
  assert.equal(seen.messages.at(-1).phase, 'error');
  assert.match(seen.messages.at(-1).message, /权限/);
  assert.equal(voice.listen(), true);
  assert.equal(seen.recorders.length, 2);
});

test('speech output cancels input, microphone interrupts speech, stale callbacks are ignored', () => {
  const { voice, seen } = setup();
  voice.listen();
  assert.equal(voice.speak('好的'), true);
  const speech = seen.speeches[0];
  assert.equal(seen.recorders[0].aborted, true);
  assert.equal(speech.voice.lang, 'zh-CN');
  voice.listen();
  assert.equal(seen.cancelled, true);
  speech.onend();
  assert.equal(seen.messages.at(-1).phase, 'listening');
  voice.interrupt();
  assert.equal(seen.recorders[1].aborted, true);
  assert.equal(seen.messages.at(-1).phase, 'idle');
});

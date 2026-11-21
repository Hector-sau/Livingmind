/* Chinese voice input and playback for the family simulator. */
(() => {
  'use strict';

  const inputErrors = {
    'not-allowed': '麦克风权限未开启。请允许浏览器使用麦克风，或直接打字。',
    'service-not-allowed': '浏览器语音服务不可用。可以直接打字。',
    'audio-capture': '没有可用的麦克风。请检查设备，或直接打字。',
    'no-speech': '没有听到清晰的话语。可以重试或打字。',
    'language-not-supported': '当前语音服务不支持中文。可以直接打字。',
    network: '浏览器语音服务连接失败。可以重试或打字。',
    aborted: '录音已中断。可以重新开始。',
  };

  function create({ onStatus = () => {}, onTranscript = () => {} } = {}) {
    const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    const synth = window.speechSynthesis;
    const capabilities = Object.freeze({
      recognition: Boolean(Recognition),
      synthesis: Boolean(synth && window.SpeechSynthesisUtterance),
    });
    let memberId = null;
    let recorder = null;
    let utterance = null;

    function status(phase, message) {
      onStatus({ phase, message });
    }

    function abortRecording() {
      const active = recorder;
      recorder = null;
      if (active) {
        try { active.abort(); } catch { /* The browser already ended this session. */ }
      }
    }

    function cancelPlayback() {
      if (!utterance) return;
      utterance = null;
      synth.cancel();
    }

    function interrupt() {
      abortRecording();
      cancelPlayback();
      status('idle', '语音已停止。');
    }

    function selectMember(next) {
      const selected = next == null ? null : String(next);
      if (memberId !== selected && (recorder || utterance)) interrupt();
      memberId = selected;
      return { memberId, identitySource: 'manual-selection', verified: false };
    }

    function listen() {
      cancelPlayback();
      if (recorder) return true;
      if (!capabilities.recognition) {
        status('unavailable', '此浏览器未提供语音识别。可以打字，或试用模拟转写。');
        return false;
      }
      let active;
      try {
        active = new Recognition();
        recorder = active;
        active.lang = 'zh-CN';
        active.continuous = false;
        active.interimResults = true;
        active.maxAlternatives = 1;
        let finalText = false;
        active.onstart = () => {
          if (recorder === active) status('listening', '正在聆听，请说中文。');
        };
        active.onresult = (event) => {
          if (recorder !== active || !event.results.length) return;
          const segments = Array.from(event.results);
          const text = segments.map((result) => result[0].transcript).join('').trim();
          if (!text) return;
          finalText = segments.every((result) => result.isFinal);
          onTranscript({ text, final: finalText, source: 'browser-asr', memberId });
        };
        active.onerror = ({ error }) => {
          if (recorder !== active) return;
          recorder = null;
          status('error', inputErrors[error] || '语音识别未完成。可以重试或打字。');
        };
        active.onend = () => {
          if (recorder !== active) return;
          recorder = null;
          status('idle', finalText ? '转写完成，确认文字后可发送。' : '录音结束，可检查输入框、重新说或打字。');
        };
        status('starting', '正在打开麦克风…');
        active.start();
        return true;
      } catch {
        abortRecording();
        status('error', '麦克风未能启动。请检查浏览器权限，或直接打字。');
        return false;
      }
    }

    function stop() {
      if (!recorder) return;
      try {
        status('stopping', '正在完成转写…');
        recorder.stop();
      } catch {
        abortRecording();
        status('idle', '录音已结束。');
      }
    }

    function example(value) {
      abortRecording();
      cancelPlayback();
      const text = String(value || '').trim();
      if (!text) return;
      onTranscript({ text, source: 'simulated-transcript', final: true, memberId });
      status('example', '模拟转写示例，可编辑后发送。');
    }

    function speak(value) {
      const text = String(value || '').trim();
      if (!text) return false;
      abortRecording();
      cancelPlayback();
      if (!capabilities.synthesis) {
        status('unavailable', '此浏览器未提供朗读功能。可查看文字回复。');
        return false;
      }
      try {
        const speech = new window.SpeechSynthesisUtterance(text);
        utterance = speech;
        speech.lang = 'zh-CN';
        const mandarin = synth.getVoices().find((voice) => /^zh[-_](CN|Hans)/i.test(voice.lang));
        if (mandarin) speech.voice = mandarin;
        speech.onend = () => {
          if (utterance !== speech) return;
          utterance = null;
          status('idle', '朗读完成。');
        };
        speech.onerror = () => {
          if (utterance !== speech) return;
          utterance = null;
          status('error', '朗读未完成。可查看文字回复。');
        };
        status('speaking', '正在朗读，可随时打断。');
        synth.speak(speech);
        return true;
      } catch {
        cancelPlayback();
        status('error', '朗读服务未能启动。可查看文字回复。');
        return false;
      }
    }

    return { capabilities, listen, stop, speak, example, interrupt, selectMember };
  }

  window.FamilyVoice = Object.freeze({ create });
})();

/* Optional recording comparison. Candidate display never switches the active resident. */
(() => {
  'use strict';
  const endpoint = '/api/family/speaker/';

  async function mount(host, members) {
    if (!host) return;
    let settings;
    try {
      const response = await fetch(endpoint + 'status', { cache: 'no-store' });
      if (!response.ok) return;
      settings = await response.json();
    } catch {
      return;
    }
    if (!host.isConnected || !settings.configured) return;
    const panel = document.createElement('details');
    const summary = document.createElement('summary');
    summary.textContent = '通过已注册声音查找成员';
    const label = document.createElement('label');
    label.className = 'field';
    label.textContent = '选择本机录音（1–30 秒 PCM WAV）';
    const file = document.createElement('input');
    file.type = 'file';
    file.accept = '.wav,audio/wav,audio/x-wav';
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'pill-btn';
    button.textContent = '比对录音';
    button.disabled = true;
    const result = document.createElement('p');
    result.className = 'dialog-copy';
    result.setAttribute('role', 'status');
    result.textContent = '声音仅在当前服务上比对，处理后清理录音。';
    label.append(file);
    panel.append(summary, label, button, result);
    host.replaceChildren(panel);
    file.onchange = () => {
      button.disabled = !file.files.length;
      result.textContent = '';
    };
    button.onclick = async () => {
      const clip = file.files[0];
      if (!clip) return;
      if (!clip.size || clip.size > settings.maxBytes) {
        result.textContent = '请上传不超过 12 MiB 的非空录音。';
        return;
      }
      button.disabled = true;
      file.disabled = true;
      result.textContent = '正在与本机注册模板比对…';
      try {
        const response = await fetch(endpoint + 'identify', {
          method: 'POST', headers: { 'Content-Type': 'audio/wav' }, body: clip,
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error?.message || '声纹服务暂时不可用。');
        const candidate = members.find((member) => member.id === data.candidate);
        result.textContent = candidate && data.comparison === 'candidate'
          ? '候选成员为' + candidate.label + '。请在“当前说话人”中手动确认。'
          : '没有足够把握判断是谁。请手动选择当前说话人。';
      } catch (error) {
        result.textContent = error.message || '比对失败，请手动选择说话人。';
      } finally {
        file.disabled = false;
        button.disabled = false;
      }
    };
  }

  window.FamilySpeakerUpload = Object.freeze({ mount });
})();

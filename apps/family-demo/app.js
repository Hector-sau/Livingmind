'use strict';

const $ = id => document.getElementById(id);
const html = value =>
  String(value ?? '').replace(
    /[&<>"']/g,
    char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char])
  );
const paths = {
  home: '<path d="m3 11 9-8 9 8"/><path d="M5 10v10h14V10M10 20v-6h4v6"/>',
  history: '<path d="M3 11a9 9 0 1 1 2 7M3 5v6h6"/><path d="M12 7v5l4 2"/>',
  voice: '<path d="M3 10v4m4-8v12m5-15v18m5-15v12m4-8v4"/>',
  sliders:
    '<path d="M3 7h9m5 0h4M3 17h5m5 0h8"/><circle cx="14.5" cy="7" r="2.5"/><circle cx="10.5" cy="17" r="2.5"/>',
  layers: '<path d="m3 7 9-4 9 4-9 4-9-4Zm0 5 9 4 9-4M3 17l9 4 9-4"/>',
  spark: '<path d="m13 3 2.1 6.2L21 12l-5.9 2.8L13 21l-2.2-6.2L5 12l5.8-2.8L13 3ZM4 2v5M2 4.5h4"/>',
  lamp: '<path d="M8 15a6 6 0 1 1 8 0l-1 2H9l-1-2ZM9 20h6M10 22h4"/>',
  desk: '<path d="m7 9 4-5 5 4-4 5-5-4Zm5 3 4 5-3 4M6 21h12M14 6l3-3"/>',
  bed: '<path d="M3 19V6m0 9h18v4m-17-9h5v4m0-4h8a4 4 0 0 1 4 4"/>',
  speaker:
    '<rect x="5" y="2" width="14" height="20" rx="2"/><circle cx="12" cy="15" r="3.5"/><circle cx="12" cy="7" r="1.5"/>',
  fan:
    '<circle cx="12" cy="12" r="2"/><path d="M12 10c-6-7-1-10 3-7 2 2 1 5-1 7m0 3c9-2 9 4 5 6-3 1-5-1-6-4m-3-2c-3 8-8 5-7 1 0-3 3-5 7-4"/>',
  curtain: '<path d="M2 3h20M4 5v15h4l-2-6c3-3 4-6 4-9m10 0v15h-4l2-6c-3-3-4-6-4-9"/>',
  ac: '<rect x="2" y="5" width="20" height="10" rx="3"/><path d="M6 12h12M7 18v2m5-2v3m5-3v2"/>',
  scan: '<path d="M8 4H4v4m12-4h4v4M4 16v4h4m12-4v4h-4M7 12h10"/>',
  moon: '<path d="M20 14a8 8 0 0 1-10-10 9 9 0 1 0 10 10Z"/>',
  tv: '<rect x="2" y="5" width="20" height="13" rx="2"/><path d="M8 21h8"/>',
  book: '<path d="M3 4c3-1 6 0 9 2 3-2 6-3 9-2v15c-3-1-6 0-9 2-3-2-6-3-9-2V4Zm9 2v15"/>',
  close: '<path d="m6 6 12 12M18 6 6 18"/>',
  check: '<path d="m4 12 5 5L20 6"/>',
  arrow: '<path d="M4 12h16m-6-6 6 6-6 6"/>',
  trace:
    '<circle cx="6" cy="5" r="2"/><circle cx="17" cy="12" r="2"/><circle cx="6" cy="19" r="2"/><path d="M6 7v10m1-10c1 4 4 5 8 5"/>',
  user: '<circle cx="12" cy="8" r="4"/><path d="M4 21c0-4 3-7 8-7s8 3 8 7"/>',
  shield: '<path d="m12 2 8 4v5c0 5-3 8-8 11-5-3-8-6-8-11V6l8-4Z"/><path d="m8 11 3 3 5-6"/>',
  tune:
    '<path d="M4 6h7m4 0h5M4 17h3m4 0h9"/><circle cx="13" cy="6" r="2"/><circle cx="9" cy="17" r="2"/>',
  mic:
    '<rect x="9" y="2" width="6" height="13" rx="3"/><path d="M5 10v2a7 7 0 0 0 14 0v-2m-7 9v3m-4 0h8"/>',
  receipt: '<path d="M6 3h12v18l-3-2-3 2-3-2-3 2V3Zm3 5h6m-6 4h6"/>',
  sun:
    '<circle cx="12" cy="12" r="4"/><path d="M12 2v3m0 14v3M2 12h3m14 0h3M5 5l2 2m10 10 2 2m0-14-2 2M7 17l-2 2"/>',
  group:
    '<circle cx="9" cy="8" r="3"/><path d="M3 20v-2a6 6 0 0 1 12 0v2m0-14a3 3 0 0 1 0 6m2 2c2 1 3 3 3 6"/>'
};
const icon = key =>
  '<svg aria-hidden="true" viewBox="0 0 24 24">' + (paths[key] || paths.home) + '</svg>';
document.querySelectorAll('[data-icon]').forEach(el => (el.innerHTML = icon(el.dataset.icon)));
const quote = key => 'data-testid="' + key + '"';
const button = (id, label, classes = 'plain-btn', symbol = '') =>
  '<button type="button" ' +
  quote(id) +
  ' data-act="' +
  id +
  '" class="' +
  classes +
  '">' +
  (symbol ? icon(symbol) : '') +
  html(label) +
  '</button>';
const activityLabels = { away: '外出', home: '在家', study: '学习中', tv: '观影中', sleep: '休息中' };
const modes = { online: '在线', offline: '离线', unknown: '待核对' };
const deviceIcon = id =>
  ({
    'living-ac': 'ac',
    'desk-light': 'desk',
    'bed-light': 'bed',
    'living-speaker': 'speaker',
    'study-fan': 'fan',
    'living-curtain': 'curtain',
    'bed-curtain': 'curtain'
  }[id] || 'lamp');
const events = {
  arrival: { type: 'arrival', person: 'mother', text: '妈妈到家', icon: 'home' },
  study: { type: 'study', person: 'child', text: '孩子开始学习', icon: 'book' },
  tv: { type: 'tv', person: 'father', text: '爸爸在客厅看电视', icon: 'tv' },
  sleep: { type: 'sleep', person: 'mother', text: '妈妈准备休息', icon: 'moon' },
  unknown: { type: 'unknown_arrival', person: null, text: '未识别成员到家', icon: 'scan' },
  shared: { type: 'study', person: 'child', room: 'living', text: '孩子到客厅阅读', icon: 'group' }
};
let state = null,
  busy = false,
  dialogKind = '',
  voice = null,
  voicePerson = 'mother',
  perRoomFilter = '';
let selectedResident = 'mother',
  toastTimer = null,
  voiceNotice = '',
  voicePhase = 'idle';
const elSheet = $('sheet');
function titleForDevice(id) {
  return state?.devices.find(d => d.id === id)?.name || id;
}
function titleForRoom(id) {
  return state?.rooms.find(r => r.id === id)?.name || '';
}
function titleForMember(id) {
  return state?.members.find(m => m.id === id)?.name || '家庭成员';
}
function targetValue(id, n) {
  return (n ?? '—') + (state?.devices.find(d => d.id === id)?.unit || '');
}
function tip(message) {
  const toast = $('toast');
  toast.textContent = message;
  toast.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (toast.hidden = true), 3200);
}
function showConnection(isOk, message) {
  $('conn-state').textContent = isOk ? '家庭网关已连接' : '家庭网关未连接';
  $('conn-dot').classList.toggle('down', !isOk);
  $('connection-warning').hidden = isOk;
  if (!isOk) $('warning-text').textContent = message || '未能读取家庭状态。请检查服务并重试。';
}
async function fetchHousehold(path, data) {
  const options =
    data === undefined
      ? {}
      : {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(data)
        };
  const response = await fetch('/api/family/' + path, { ...options, cache: 'no-store' });
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const message =
      payload?.error?.message ||
      (typeof payload?.detail === 'string' && payload.detail) ||
      '家庭服务未完成此请求。';
    throw Object.assign(new Error(message), { api: true, status: response.status });
  }
  if (!Array.isArray(payload?.members)) throw new Error('服务返回了未识别的数据。');
  return payload;
}

async function call(path, data) {
  if (busy) return false;
  busy = true;
  document.body.classList.add('pending');
  try {
    let latest;
    try {
      latest = await fetchHousehold(path, data);
    } catch (error) {
      if (path !== 'decision' || ![403, 409].includes(error.status)) throw error;
      // Another tab can replace a proposal with a different owner's proposal.
      // Read the current household once. Never resend the user's decision.
      latest = await fetchHousehold('state');
      if (latest.suggestion?.id === data.suggestionId) throw error;
      state = latest;
      showConnection(true);
      closeSheet();
      render();
      tip('原建议已失效，已更新家庭状态。请重新核对。');
      return false;
    }
    // A resident may open an editor while a focus/reconnect refresh is in flight.
    // Never attach that draft to a proposal the editor did not show.
    if (
      data === undefined &&
      state?.suggestion?.id !== latest.suggestion?.id &&
      ['edit', 'trace', 'voice'].includes(dialogKind)
    ) {
      closeSheet();
      tip('家庭建议已经更新，请重新核对。');
    }
    state = latest;
    showConnection(true);
    render();
    return true;
  } catch (err) {
    if (err.api) {
      tip(String(err.message));
      if (elSheet.open) {
        let feedback = $('dialog-error');
        if (!feedback) {
          feedback = document.createElement('p');
          feedback.id = 'dialog-error';
          feedback.className = 'warning';
          $('sheet-body').append(feedback);
        }
        feedback.textContent = String(err.message);
      }
    } else {
      showConnection(false, '家庭网关连接中断，当前显示上次读取的状态。');
      tip(err.message || '请求失败');
    }
    return false;
  } finally {
    busy = false;
    document.body.classList.remove('pending');
  }
}
function navigate(name) {
  const history = name === 'history';
  $('home-view').hidden = history;
  $('history-view').hidden = !history;
  $('crumb-current').textContent = history ? '服务记录' : '家庭空间';
  document.querySelectorAll('[data-view]').forEach(btn => {
    const on = btn.dataset.view === name;
    btn.classList.toggle('selected', on);
    btn.setAttribute('aria-current', on ? 'page' : 'false');
  });
}
function render() {
  if (!state) return;
  const members = state.members,
    devices = state.devices || [],
    atHome = members.filter(m => m.activity !== 'away');
  $('resident').innerHTML = members
    .map(m => '<option value="' + html(m.id) + '">' + html(m.name) + '</option>')
    .join('');
  $('resident').value = selectedResident;
  $('room-filter').innerHTML =
    '<option value="">全部空间</option>' +
    state.rooms.map(r => '<option value="' + html(r.id) + '">' + html(r.name) + '</option>').join('');
  $('room-filter').value = perRoomFilter;
  const roomLights = { living: 'living-light', study: 'desk-light', bedroom: 'bed-light' };
  $('room-pins').innerHTML = state.rooms
    .map(room => {
      const light = devices.find(d => d.id === roomLights[room.id]);
      if (!light) return '';
      const level = Math.max(0, Math.min(1, Number(light.lastObserved || 0) / 100));
      const description =
        (light.mode === 'online' ? '灯光' : '上次') + ' ' + targetValue(light.id, light.lastObserved);
      return (
        '<button class="map-pin pin-' +
        html(room.id) +
        '" data-act="filter-' +
        html(room.id) +
        '" data-testid="pin-' +
        html(room.id) +
        '" aria-label="' +
        html(room.name + '，' + description) +
        '" style="--level:' +
        level +
        '"><i></i>' +
        html(room.name) +
        '<small>' +
        html(description) +
        '</small></button>'
      );
    })
    .join('');
  $('room-time').textContent = state.time || state.timeline[0]?.time || '--:--';
  $('room-summary').textContent =
    '模拟第 ' +
    state.day +
    ' 晚 · ' +
    (atHome.length ? atHome.length + ' 位家庭成员在家' : '家中暂时无人');
  $('members-meta').textContent = atHome.length + ' / ' + members.length + ' 人在家';
  $('members').innerHTML = members
    .map(
      m =>
        '<article class="member"><div class="avatar ' +
        html(m.id) +
        '">' +
        icon(m.id === 'child' ? 'book' : 'user') +
        '</div><div><h3>' +
        html(m.name) +
        '</h3><p>' +
        html(
          [m.activityLabel || activityLabels[m.activity] || m.activity, titleForRoom(m.roomId)]
            .filter(Boolean)
            .join(' · ')
        ) +
        '</p><small class="member-pref">' +
        html(m.preference) +
        '</small></div></article>'
    )
    .join('');
  $('devices').innerHTML = devices
    .filter(d => !perRoomFilter || d.roomId === perRoomFilter)
    .map(
      d =>
        '<button type="button" class="device" data-act="inspect-' +
        html(d.id) +
        '" data-testid="device-' +
        html(d.id) +
        '"><div class="device-head">' +
        icon(deviceIcon(d.id)) +
        '<span class="device-state ' +
        (d.mode === 'online' ? '' : 'problem') +
        '">' +
        html((modes[d.mode] || d.mode) + (d.mode === 'online' ? '' : ' · 上次读数')) +
        '</span></div><div><strong>' +
        html(d.name) +
        '</strong><span class="val">' +
        html(d.value ?? '—') +
        '</span><small>' +
        html(d.unit) +
        '</small></div></button>'
    )
    .join('');
  const history = state.timeline || [];
  $('history-count').textContent = history.length ? String(history.length) : '';
  $('history-meta').textContent = history.length + ' 条';
  $('timeline').innerHTML = history.length
    ? history
        .map(
          t =>
            '<article class="time-row"><time>' +
            html(t.time) +
            '</time><i></i><div><h3>' +
            html(t.title) +
            '</h3><p>' +
            html(t.detail) +
            '</p></div></article>'
        )
        .join('')
    : '<p class="empty">尚无服务记录。</p>';
  renderProposal();
}
function renderProposal() {
  const s = state.suggestion,
    receipts = state.receipts || [];
  const indicator = $('service-indicator');
  indicator.classList.toggle('active', !!s);
  indicator.textContent = s ? '待确认' : state.muted ? '今晚已静音' : '观察中';
  const body = $('proposal');
  if (s) {
    let acts = (s.actions || [])
      .map(
        a =>
          '<span class="target">' +
          html(titleForDevice(a.deviceId)) +
          ' ' +
          html(targetValue(a.deviceId, a.value)) +
          '</span>'
      )
      .join('');
    body.innerHTML =
      '<h3 data-testid="proposal-title">' +
      html(s.title) +
      '</h3><p>' +
      html(s.reason) +
      '</p><div class="targets">' +
      acts +
      '</div><div class="action-row">' +
      button('action-confirm', '确认执行', 'primary-btn', 'check') +
      button('action-edit', '调整方案', 'pill-btn', 'tune') +
      button('action-dismiss', '跳过', 'plain-btn') +
      '</div><div class="service-tools">' +
      button('action-trace', '协作过程', 'trace-toggle', 'trace') +
      button('action-snooze', '稍后提醒', 'trace-toggle', 'history') +
      button('action-mute', '今晚不再提醒', 'trace-toggle', 'moon') +
      '</div>';
  } else {
    const hasExecution = receipts.length > 0 && ['confirmed', 'incomplete'].includes(state.lastOutcome);
    const recent = state.timeline?.[0];
    let title = '等待合适的服务时机';
    let copy = '家庭成员到家、学习或休息时，空间会结合个人偏好判断是否提出建议。';
    if (state.muted) {
      title = '今晚已开启免打扰';
      copy = '今晚的主动建议已暂停，成员和设备状态仍可查看。';
    } else if (hasExecution) {
      const complete = receipts.every(receipt => receipt.status === 'confirmed');
      title = complete ? '设备调整已完成' : '部分设备尚未确认';
      copy = complete
        ? '已按确认的方案执行，可逐台核对目标与回读。'
        : '请逐台核对目标、回读和未完成的原因。';
    } else if (recent && !['ready', 'reset', 'idle'].includes(state.lastOutcome)) {
      title = recent.title;
      copy = recent.detail;
    }
    body.innerHTML =
      '<div class="resting-art" aria-hidden="true">' +
      Array.from({ length: 12 }, () => '<span></span>').join('') +
      '</div><h3 data-testid="proposal-title">' +
      html(title) +
      '</h3><p>' +
      html(copy) +
      '</p>' +
      (hasExecution
        ? button('action-receipts', '查看设备回执', 'pill-btn intro-btn', 'receipt')
        : button('open-simulator', '模拟空间事件', 'pill-btn intro-btn', 'sliders'));
  }
}
function openSheet(kind, kicker, title, content) {
  dialogKind = kind;
  $('sheet-kicker').textContent = kicker;
  $('sheet-title').textContent = title;
  $('sheet-body').innerHTML = content;
  if (!elSheet.open) elSheet.showModal();
  elSheet.scrollTop = 0;
}
function closeSheet() {
  if (elSheet.open) elSheet.close();
}
elSheet.addEventListener('close', () => {
  if (dialogKind === 'voice') voice?.interrupt();
  dialogKind = '';
});
elSheet.addEventListener('click', e => {
  if (e.target !== elSheet) return;
  const rect = elSheet.getBoundingClientRect();
  if (e.clientX < rect.left || e.clientX > rect.right || e.clientY < rect.top || e.clientY > rect.bottom)
    closeSheet();
});
$('sheet-close').onclick = closeSheet;
function presenter() {
  if (!state) {
    tip('请先连接家庭网关');
    return;
  }
  const choices = Object.entries(events)
    .map(([id, o]) => button('sim-' + id, o.text, 'event-option', o.icon))
    .join('');
  const opts = state.devices
    .map(d => '<option value="' + html(d.id) + '">' + html(d.name) + '</option>')
    .join('');
  openSheet(
    'presenter',
    'SCENE SIMULATOR',
    '场景模拟器',
    '<p class="dialog-copy">选择一个模拟事件，观察住户收到的建议和设备回读。</p><div class="event-grid">' +
      choices +
      '</div><details class="fixture-tools" data-testid="fault-controls"><summary>设备与回执模拟</summary><div class="fixture-row"><label class="field">设备<select id="fault-device" ' +
      quote('fault-device') +
      '>' +
      opts +
      '</select></label><label class="field">状态<select id="fault-mode" ' +
      quote('fault-mode') +
      '><option value="online">在线</option><option value="offline">离线</option><option value="unknown">回执未知</option></select></label>' +
      button('fault-apply', '应用', 'plain-btn') +
      '</div></details><div class="sheet-footer">' +
      button('reset-demo', '重置演示', 'plain-btn') +
      button('next-day', '进入下一晚', 'pill-btn', 'sun') +
      '</div>'
  );
}
const uid = () =>
  globalThis.crypto?.randomUUID?.() ||
  Date.now() +
    '-' +
    Math.random()
      .toString(36)
      .slice(2);
async function eventAction(opts, origin = 'simulated') {
  if (opts.person) {
    selectedResident = opts.person;
    voicePerson = opts.person;
    $('resident').value = selectedResident;
  }
  const ok = await call('events', {
    eventId: uid(),
    type: opts.type,
    ...(opts.person ? { memberId: opts.person } : {}),
    ...(opts.room ? { roomId: opts.room } : {}),
    source: origin
  });
  if (ok) {
    closeSheet();
    navigate('home');
    tip(state.timeline?.[0]?.title || '已接收事件');
  }
}
function edit() {
  const s = state.suggestion;
  if (!s) return;
  const choices = (s.actions || [])
    .map(
      (a, i) =>
        '<label class="choice"><input type="radio" name="edit-choice" value="' +
        html(a.deviceId) +
        '" ' +
        quote('edit-device-' + html(a.deviceId)) +
        (i === 0 ? ' checked' : '') +
        '>仅调' +
        html(titleForDevice(a.deviceId)) +
        '至 ' +
        html(targetValue(a.deviceId, a.value)) +
        '</label>'
    )
    .join('');
  openSheet(
    'edit',
    'PLAN ADJUSTMENT',
    '调整当前方案',
    '<p class="dialog-copy">选择设备或用一句话修改。用“这次只……”限定当前方案，用“今晚只……”应用到当晚同一场景。修改后仍需确认。</p>' +
      choices +
      button('edit-save', '仅保留所选动作', 'pill-btn') +
      '<label class="field">用一句话调整<input id="edit-text" ' +
      quote('edit-text') +
      ' placeholder="今晚只调客厅灯到 35%" maxlength="180"></label><div class="sheet-footer">' +
      button('edit-text-save', '预览文字修改', 'primary-btn', 'arrow') +
      '</div>'
  );
}
async function decide(decision, extra = {}, memberId) {
  const s = state.suggestion;
  if (!s) {
    tip('当前没有待处理的主动建议');
    return false;
  }
  const ok = await call('decision', {
    suggestionId: s.id,
    decision,
    memberId: memberId || selectedResident,
    ...extra
  });
  if (ok) {
    navigate('home');
    if (state.decisionReplayed && state.decisionResult) {
      const result = state.decisionResult;
      if (result.decision === 'confirm') {
        if (dialogKind === 'voice') voice?.interrupt();
        receipts(result.receipts, '原建议的执行回执');
      } else {
        closeSheet();
        tip('原建议已处理。已同步当前家庭状态。');
      }
      return true;
    }
    closeSheet();
    tip(
      decision === 'edit'
        ? state.suggestion?.scope === 'once'
          ? '本次方案已修改，请核对后确认。'
          : '今晚的方案已修改，请核对后确认。'
        : state.timeline?.[0]?.title || '已完成'
    );
    return true;
  }
  return false;
}
function trace() {
  const s = state.suggestion;
  if (!s) return;
  const rows = (s.trace || [])
    .map(
      row =>
        '<div class="trace-row"><span>' +
        icon('trace') +
        '</span><div><b>' +
        html(row.agent) +
        '</b><p>' +
        html(row.detail) +
        '</p></div></div>'
    )
    .join('');
  openSheet(
    'trace',
    'AGENT WORKFLOW',
    '协作过程',
    rows || '<p class="empty">当前方案没有可展示的协作记录。</p>'
  );
}
function receipts(results = state.receipts, title = '设备执行回执') {
  const names = {
    confirmed: '已回读',
    offline: '设备离线',
    unknown: '回执未知',
    mismatch: '读数不符',
    rejected: '未执行'
  };
  const rows = (results || [])
    .map(
      r =>
        '<div class="trace-row"><span>' +
        icon(deviceIcon(r.deviceId)) +
        '</span><div><b>' +
        html(titleForDevice(r.deviceId)) +
        ' · ' +
        html(names[r.status] || r.status) +
        '</b><p>目标 ' +
        html(targetValue(r.deviceId, r.requested)) +
        ' · ' +
        (r.observed != null
          ? '回读 ' + html(targetValue(r.deviceId, r.observed))
          : '尚无可确认的回读值') +
        '</p></div></div>'
    )
    .join('');
  openSheet('receipts', 'DEVICE RECEIPTS', title, rows || '<p class="empty">尚无设备执行回执。</p>');
}
function speechDraftPending() {
  // Interim text can look like a complete confirmation before ASR revises it.
  return ['starting', 'listening', 'stopping'].includes(voicePhase) || voiceNotice === 'asr-interim';
}
function refreshSpeechSubmit() {
  const button = document.querySelector('[data-act="speech-send"]');
  if (button) button.disabled = speechDraftPending();
}
function initVoice() {
  if (!voice && window.FamilyVoice) {
    voice = window.FamilyVoice.create({
      onStatus: ({ message, phase }) => {
        voicePhase = phase;
        if (dialogKind !== 'voice' || !$('voice-status')) return;
        if (phase === 'starting') {
          voiceNotice = '';
          $('speech-input').value = '';
        }
        $('voice-status').textContent = message || '';
        if (phase === 'idle' && voiceNotice === 'asr-interim') {
          $('voice-status').textContent = '未收到最终转写。请重新说话，或手动修改文字后提交。';
        }
        refreshSpeechSubmit();
      },
      onTranscript: ({ text, source, final, memberId }) => {
        if (dialogKind === 'voice' && memberId === voicePerson && $('speech-input')) {
          $('speech-input').value = text;
          voiceNotice = final ? source : 'asr-interim';
          refreshSpeechSubmit();
          if ($('voice-status'))
            $('voice-status').textContent =
              source === 'simulated-transcript'
                ? '示例文本已填入，请核对后提交。'
                : final
                ? '转写完成，请核对后提交。'
                : '正在转写…';
        }
      }
    });
  }
}
function voiceSheet() {
  if (!state) {
    tip('请先连接家庭网关');
    return;
  }
  initVoice();
  voicePerson = selectedResident;
  voiceNotice = '';
  voice?.selectMember(voicePerson);
  const options = state.members
    .map(
      m =>
        '<option value="' +
        html(m.id) +
        '" ' +
        (voicePerson === m.id ? 'selected' : '') +
        '>' +
        html(m.name) +
        '</option>'
    )
    .join('');
  openSheet(
    'voice',
    'VOICE INPUT',
    '语音交互',
    '<p class="dialog-copy">当前说话人由手动选择。你可以说话或打字，核对文字后再提交。</p><label class="field">当前说话人<select id="voice-member" ' +
      quote('voice-member') +
      '>' +
      options +
      '</select></label><label class="field">这次想做什么？<input id="speech-input" ' +
      quote('speech-input') +
      ' placeholder="例如：我到家了、我想休息、确认方案" maxlength="180"></label><div class="secondary-tools">' +
      button('voice-listen', '开始说话', 'pill-btn', 'mic') +
      button('voice-stop', '打断语音', 'plain-btn') +
      button('voice-example', '填入示例', 'plain-btn') +
      '</div><div class="voice-status" id="voice-status" role="status">' +
      (voice?.capabilities.recognition ? '' : '当前浏览器可用文字输入。') +
      '</div><div class="sheet-footer">' +
      button('voice-read', '朗读当前建议', 'plain-btn', 'voice') +
      button('speech-send', '提交文字', 'primary-btn', 'arrow') +
      '</div><div id="speaker-check"></div>'
  );
  window.FamilySpeakerUpload?.mount(
    $('speaker-check'),
    state.members.map(m => ({ id: m.id, label: m.name }))
  );
  $('voice-member').onchange = e => {
    voicePerson = e.target.value;
    selectedResident = voicePerson;
    $('resident').value = selectedResident;
    voice?.selectMember(voicePerson);
    voiceNotice = '';
    $('speech-input').value = '';
    $('voice-status').textContent = '已切换说话人，请重新说话或输入。';
    $('dialog-error')?.remove();
    refreshSpeechSubmit();
  };
  $('speech-input').onkeydown = e => {
    if (e.key === 'Enter') submitSpeech();
  };
  $('speech-input').oninput = () => {
    if (speechDraftPending()) {
      voice?.interrupt();
      $('voice-status').textContent = '已切换为手动编辑，请核对文字后提交。';
    }
    voiceNotice = 'typed';
    refreshSpeechSubmit();
  };
  refreshSpeechSubmit();
}
async function submitSpeech() {
  const input = $('speech-input');
  if (!input || speechDraftPending()) return;
  const txt = input.value.trim().replace(/[。！!，,]+$/g, '');
  if (!txt) {
    $('voice-status').textContent = '请说一句话，或在输入框中打字。';
    return;
  }
  voice?.stop();
  if (/^(?:稍后|晚点)(?:再)?(?:提醒)?$/.test(txt)) {
    await decide('snooze', {}, voicePerson);
    return;
  }
  if (/^(?:请)?(?:今晚)?(?:静音|不再提醒|免打扰)$/.test(txt)) {
    await decide('mute', {}, voicePerson);
    return;
  }
  if (/^(?:请)?(?:跳过|忽略|不用了|先不用)(?:这条建议)?$/.test(txt)) {
    await decide('dismiss', {}, voicePerson);
    return;
  }
  if (/^(?:请|我)?(?:确认|同意|执行)(?:这条)?(?:方案|建议|执行)?$/.test(txt)) {
    await decide('confirm', {}, voicePerson);
    return;
  }
  // A new event must be an entire, unambiguous utterance. Mixed requests belong
  // to the current proposal’s bounded editor and can never imply confirmation.
  const simple = txt.replace(/[，。！,!？?\s]/g, '');
  const namedMember = state.members.find(m => simple.startsWith(m.name));
  if (namedMember && namedMember.id !== voicePerson) {
    $('voice-status').textContent =
      '这句话提到' +
      namedMember.name +
      '，当前选择的是' +
      titleForMember(voicePerson) +
      '。请切换说话人后重新输入，或用第一人称描述自己的活动。';
    return;
  }
  const eventPatterns = [
    ['arrival', /^(?:我|我们)?(?:刚刚|刚|已经)?(?:到家|回家)(?:了|啦)?$/],
    [
      'study',
      /^(?:我|孩子)?(?:准备|开始|想要|想|要|正在|在)?(?:在)?(?:客厅|书房)?(?:学习|阅读|看书)(?:了)?$/
    ],
    ['tv', /^(?:我|爸爸)?(?:准备|开始|想要|想|要|正在|在)?(?:客厅)?(?:看电视|观影|看电影)(?:了)?$/],
    ['sleep', /^(?:我|妈妈)?(?:准备|开始|想要|想|要|正在|在)?(?:睡觉|入睡|休息)(?:了)?$/]
  ];
  const kind = eventPatterns.find(([, pattern]) => pattern.test(simple))?.[0];
  if (!kind) {
    if (state.suggestion) {
      await decide('edit', { text: txt }, voicePerson);
    } else {
      $('voice-status').textContent =
        '可以描述到家、学习、观影或休息。有待确认建议时，也可以说出本次修改要求。';
    }
    return;
  }
  await eventAction(
    {
      type: kind,
      person: voicePerson,
      ...(kind === 'study' && txt.includes('客厅') ? { room: 'living' } : {})
    },
    voiceNotice === 'simulated-transcript'
      ? 'simulated-transcript'
      : voiceNotice === 'browser-asr'
      ? 'browser-asr'
      : 'resident-input'
  );
}
async function action(id) {
  if (busy) return;
  if (id.startsWith('sim-')) {
    const evt = events[id.slice(4)];
    if (evt) await eventAction(evt);
    return;
  }
  if (id.startsWith('filter-')) {
    perRoomFilter = id.slice(7);
    render();
    $('devices').scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    $('room-filter').focus({ preventScroll: true });
    return;
  }
  if (id.startsWith('inspect-')) {
    const d = state.devices.find(item => item.id === id.slice(8));
    if (!d) return;
    const c = d.capability,
      bounds = c?.valueRange;
    openSheet(
      'device',
      'VIRTUAL DEVICE',
      d.name,
      '<p class="dialog-copy">' +
        html(titleForRoom(d.roomId)) +
        ' · 虚拟网关 · ' +
        html(modes[d.mode]) +
        '</p><div class="trace-row"><span>' +
        icon(deviceIcon(d.id)) +
        '</span><div><b>最近一次已知读数</b><p>' +
        html(targetValue(d.id, d.lastObserved)) +
        '</p></div></div><div class="trace-row"><span>' +
        icon('sliders') +
        '</span><div><b>设备能力</b><p>' +
        html(c?.service) +
        ' / ' +
        html(c?.property) +
        ' · SIID ' +
        html(c?.siid) +
        ' / PIID ' +
        html(c?.piid) +
        '</p><p>' +
        html(bounds ? bounds[0] + '–' + bounds[1] + d.unit + '，步长 ' + bounds[2] : '') +
        '</p></div></div>'
    );
    return;
  }
  if (id === 'open-simulator') return presenter();
  if (id === 'action-confirm') return decide('confirm');
  if (id === 'action-dismiss') return decide('dismiss');
  if (id === 'action-mute') return decide('mute');
  if (id === 'action-snooze') return decide('snooze');
  if (id === 'action-edit') return edit();
  if (id === 'action-trace') return trace();
  if (id === 'action-receipts') return receipts();
  if (id === 'edit-save') {
    const device = document.querySelector('input[name="edit-choice"]:checked');
    if (device) await decide('edit', { onlyDeviceId: device.value });
    return;
  }
  if (id === 'edit-text-save') {
    const txt = $('edit-text').value.trim();
    if (txt) await decide('edit', { text: txt });
    else tip('请先输入修改要求');
    return;
  }
  if (id === 'fault-apply') {
    const ok = await call('devices', { deviceId: $('fault-device').value, mode: $('fault-mode').value });
    if (ok) {
      closeSheet();
      tip('设备状态已更新');
    }
    return;
  }
  if (id === 'next-day' || id === 'reset-demo') {
    const ok = await call(id === 'next-day' ? 'next-day' : 'reset', {});
    if (ok) {
      closeSheet();
      navigate('home');
      tip(id === 'next-day' ? '已进入下一晚' : '已重置模拟家庭');
    }
    return;
  }
  if (id === 'speech-send') return submitSpeech();
  if (id === 'voice-listen') {
    if (voice?.capabilities.recognition) voice.listen();
    else $('voice-status').textContent = '当前浏览器不支持语音识别，请打字输入。';
    return;
  }
  if (id === 'voice-stop') {
    if (['listening', 'starting'].includes(voicePhase)) voice?.stop();
    else voice?.interrupt();
    return;
  }
  if (id === 'voice-read') {
    if (voice?.capabilities.synthesis)
      voice.speak(
        [state.suggestion?.title, state.suggestion?.reason].filter(Boolean).join('，') ||
          $('proposal').querySelector('h3')?.textContent ||
          '目前没有待处理的建议'
      );
    else $('voice-status').textContent = '当前浏览器未提供语音播报。';
    return;
  }
  if (id === 'voice-example') {
    const txt = state.suggestion
      ? '确认方案'
      : voicePerson === 'father'
      ? '我想看电视'
      : voicePerson === 'child'
      ? '我想学习'
      : '我到家了';
    if (voice) voice.example(txt);
    else $('speech-input').value = txt;
    return;
  }
}
document.addEventListener('click', e => {
  const b = e.target.closest('button[data-act]');
  if (b) action(b.dataset.act);
});
document.querySelectorAll('[data-view]').forEach(b => (b.onclick = () => navigate(b.dataset.view)));
document.querySelector('.brand').onclick = e => {
  e.preventDefault();
  navigate('home');
};
$('presenter-open').onclick = presenter;
$('voice-open').onclick = voiceSheet;
$('retry-connect').onclick = () => call('state');
$('resident').onchange = e => {
  selectedResident = e.target.value;
  voicePerson = selectedResident;
  voice?.selectMember(selectedResident);
};
$('room-filter').onchange = e => {
  perRoomFilter = e.target.value;
  render();
};
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'visible' && state && !elSheet.open) call('state');
});
call('state');

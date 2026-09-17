// Front-end mirror of the backend agents (orchestrator router, space execution parser, energy rules,
// adjustment rule). Pure functions; used only by the mock API. Keep in sync with:
//   backend/app/agents/orchestrator/agent.py, agents/space_execution/agent.py,
//   backend/app/energy/rules.py, backend/app/rules/rest_rule.py, backend/app/rules/night_rule.py
import type { DeviceAction, DeviceState, EnergyAdvice, EnergyMode, RestPreference, ScheduledStep } from '../types';
import { DEEP_NIGHT_AC_RAISE_C, NIGHT_START_LOCAL, WAKE_LIGHT_MAX } from './seed';

export type Intent = 'rest' | 'device_command' | 'status' | 'other';

const REST = /休息|睡|躺|困|累|午睡|歇|放松|安静/;
const DEVICE = /灯|空调|窗帘/;
const ACTION = /开|关|调|设|拉|合|到/;
const STATUS = /现在|状态|多少|几度|怎么样了|情况/;

export function routeIntent(text: string): Intent {
  const t = text.replace(/\s/g, '');
  if (REST.test(t)) return 'rest';
  if (DEVICE.test(t) && ACTION.test(t)) return 'device_command';
  if (STATUS.test(t) && (DEVICE.test(t) || /房间|卧室|温度/.test(t))) return 'status';
  return 'other';
}

export const INTENT_LABEL: Record<Intent, string> = {
  rest: '休息请求',
  device_command: '设备指令',
  status: '状态查询',
  other: '其他话题',
};

const CN: Record<string, number> = { 二: 2, 两: 2, 三: 3, 四: 4, 五: 5, 六: 6, 七: 7, 八: 8, 九: 9, 一: 1 };

function numberIn(text: string): number | null {
  const m = text.match(/(\d+(?:\.\d+)?)/);
  if (m) return Number(m[1]);
  const c = text.match(/([二两三四五六七八九]?十[一二三四五六七八九]?)/);
  if (!c) return null;
  const s = c[1];
  const tens = s[0] === '十' ? 1 : CN[s[0]] ?? 1;
  const ones = s[s.length - 1] === '十' ? 0 : CN[s[s.length - 1]] ?? 0;
  return tens * 10 + ones;
}

export interface CommandTarget {
  light: number | null;
  ac: number | null;
  curtain: number | null;
  phrases: string[];
}

export function parseCommand(text: string, nightLightMax: number): CommandTarget {
  const t = text.replace(/\s/g, '');
  const out: CommandTarget = { light: null, ac: null, curtain: null, phrases: [] };
  const afterLight = t.includes('灯') ? t.split('灯').slice(1).join('灯') : '';
  if (/关灯|灯关|熄灯|把灯关/.test(t)) {
    out.light = 0;
    out.phrases.push('关灯');
  } else if (t.includes('灯') && /调到|开到|设到|调成|亮度/.test(t) && numberIn(afterLight) !== null) {
    out.light = numberIn(afterLight);
    out.phrases.push('调灯光');
  } else if (/开灯|打开灯|把灯打开/.test(t)) {
    out.light = nightLightMax;
    out.phrases.push('开灯');
  }
  if (t.includes('空调')) {
    const n = numberIn(t.split('空调').slice(1).join('空调'));
    if (n !== null) {
      out.ac = n;
      out.phrases.push('调空调');
    }
  }
  if (t.includes('窗帘')) {
    const rest = t.split('窗帘').slice(1).join('窗帘');
    const n = numberIn(rest);
    if (n !== null && /开到|调到|留/.test(rest)) {
      out.curtain = n;
      out.phrases.push('调窗帘');
    } else if (/关|拉上|合上/.test(t)) {
      out.curtain = 0;
      out.phrases.push('关窗帘');
    } else if (/打开|拉开|开/.test(t)) {
      out.curtain = 100;
      out.phrases.push('开窗帘');
    }
  }
  return out;
}

export const LABEL = {
  light: (v: number) => `灯光亮度调到 ${v}%`,
  ac: (v: number) => `空调设定 ${v}°C`,
  curtain: (v: number) => (v === 0 ? '窗帘全部关闭' : `窗帘开到 ${v}%`),
};
const COMMAND = { light: 'set_brightness', ac: 'set_target_temperature', curtain: 'set_open_percent' } as const;

export function restActions(target: RestPreference, newId: (p: string) => string, nightLightMax: number) {
  const notes: string[] = [];
  let light = target.lightBrightness;
  if (light > nightLightMax) {
    notes.push(`空间规则：休息时灯光不超过 ${nightLightMax}%，已从 ${light}% 调整`);
    light = nightLightMax;
  }
  const curtainLabel = target.curtainOpenPercent === 0 ? '窗帘全部关闭' : `窗帘保留 ${target.curtainOpenPercent}%`;
  const actions: DeviceAction[] = [
    { actionId: newId('a'), device: 'light', command: 'set_brightness', value: light, label: LABEL.light(light) },
    { actionId: newId('a'), device: 'ac', command: 'set_target_temperature', value: target.acTargetTempC, label: LABEL.ac(target.acTargetTempC) },
    { actionId: newId('a'), device: 'curtain', command: 'set_open_percent', value: target.curtainOpenPercent, label: curtainLabel },
  ];
  return { actions, notes };
}

export function commandActions(target: CommandTarget, state: DeviceState, newId: (p: string) => string) {
  const current = { light: state.lightBrightness, ac: state.acTargetTempC, curtain: state.curtainOpenPercent };
  const actions: DeviceAction[] = [];
  const notes: string[] = [];
  for (const device of ['light', 'ac', 'curtain'] as const) {
    const value = target[device];
    if (value === null) continue;
    if (value === current[device]) {
      notes.push(`${LABEL[device](value)}：已经是这个状态`);
      continue;
    }
    actions.push({ actionId: newId('a'), device, command: COMMAND[device], value, label: LABEL[device](value) });
  }
  return { actions, notes };
}

const LIMITS = {
  set_brightness: [0, 100, true],
  set_target_temperature: [16, 30, false],
  set_open_percent: [0, 100, true],
} as const;

export function precheck(actions: DeviceAction[]) {
  const allowed: DeviceAction[] = [];
  const problems: string[] = [];
  for (const a of actions) {
    const [min, max, integer] = LIMITS[a.command];
    if (a.value < min || a.value > max) problems.push(`${a.label}：参数超出范围：${a.value}（允许 ${min}–${max}）`);
    else if (integer && !Number.isInteger(a.value)) problems.push(`${a.label}：参数必须是整数`);
    else allowed.push(a);
  }
  return { allowed, problems };
}

// ---- energy rules ----

export const OUTDOOR_TEMP_C = 29;
const PEAK = (h: number) => h >= 18 && h < 23;

export function estimateLoadKw(ac: number, light: number, outdoor = OUTDOOR_TEMP_C): number {
  return Math.round((Math.max(0, outdoor - ac) * 0.12 + (light / 100) * 0.03) * 100) / 100;
}

export function powerTier(kw: number): EnergyAdvice['tierAfter'] {
  return kw < 0.5 ? 'low' : kw < 0.9 ? 'medium' : 'high';
}

export const TIER_LABEL = { low: '低', medium: '中', high: '高' } as const;

export function energyAdvise(target: RestPreference, mode: EnergyMode, localHour: number): EnergyAdvice {
  const req = target.acTargetTempC;
  const low = Math.max(16, req - 1);
  const high = Math.min(30, req + 1);
  const tariff = PEAK(localHour) ? 'peak' : 'offpeak';
  const cooling = OUTDOOR_TEMP_C > req;
  let rec = req;
  let reason: string;
  if (cooling && tariff === 'peak') {
    rec = Math.min(req + 0.5, high);
    reason = `室外约 ${OUTDOOR_TEMP_C}°C、当前为高峰电价时段，在舒适范围 ${low}–${high}°C 内把空调设定提高 ${rec - req}°C 可降低制冷负荷`;
  } else if (cooling) {
    reason = '非高峰时段，保持体验目标温度';
  } else {
    reason = '室外不高于设定温度，不需要制冷，保持体验目标';
  }
  const applied = mode === 'eco' && rec !== req;
  if (rec !== req && !applied) reason += '；当前为“舒适优先”，只给建议不改设定';
  const before = estimateLoadKw(req, target.lightBrightness);
  const after = estimateLoadKw(applied ? rec : req, target.lightBrightness);
  return {
    mode,
    tariff,
    outdoorTempC: OUTDOOR_TEMP_C,
    comfortMinC: low,
    comfortMaxC: high,
    requestedAcC: req,
    recommendedAcC: rec,
    applied,
    loadKwBefore: before,
    loadKwAfter: after,
    tierBefore: powerTier(before),
    tierAfter: powerTier(after),
    reason: `前端模拟：${reason}`,
    source: 'frontend_mock',
  };
}

// ---- adjustment rule ----

export function adjustmentTarget(prefAc: number, currentAc: number, roomTempC: number): { next: number; summary: string } {
  let next = currentAc;
  let why: string;
  if (roomTempC >= currentAc + 2) {
    next = Math.max(currentAc - 1, prefAc - 3, 16);
    why = `室温 ${roomTempC}°C 高于设定 ${currentAc}°C`;
  } else if (roomTempC <= currentAc - 2) {
    next = Math.min(currentAc + 1, prefAc + 3, 30);
    why = `室温 ${roomTempC}°C 低于设定 ${currentAc}°C`;
  } else {
    return { next, summary: `室温 ${roomTempC}°C 与设定 ${currentAc}°C 接近，无需调整` };
  }
  return next === currentAc
    ? { next, summary: `${why}，但已到偏好允许的调整边界` }
    : { next, summary: `${why}，空调调整到 ${next}°C` };
}

// ---- overnight schedule on a simulated clock (backend/app/rules/night_rule.py) ----

const DAY = 24 * 60;
const toMin = (hhmm: string) => {
  const [h, m] = hhmm.split(':').map(Number);
  return h * 60 + m;
};
const START_MIN = toMin(NIGHT_START_LOCAL);

export function nightOffset(hhmm: string): number {
  return (((toMin(hhmm) - START_MIN) % DAY) + DAY) % DAY;
}

export function nightClockLabel(offsetMin: number): string {
  const total = (START_MIN + offsetMin) % DAY;
  return `${String(Math.floor(total / 60)).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`;
}

type Device = DeviceAction['device'];

/** Five timed steps: sleep, deep night, three-step wake-up ending at WAKE_TIME_LOCAL. */
export function nightSchedule(
  target: RestPreference,
  preference: RestPreference,
  nightLightMax: number,
  newId: (p: string) => string,
  wakeTime: '06:30' | '07:00' | '07:30' = '07:00',
): ScheduledStep[] {
  const ac = target.acTargetTempC;
  const deepAc = Math.min(ac + DEEP_NIGHT_AC_RAISE_C, preference.acTargetTempC + 3, 30);
  const wakeLight = Math.min(WAKE_LIGHT_MAX, nightLightMax);
  const wake = nightOffset(wakeTime);
  const curtain = target.curtainOpenPercent;
  const specs: [number, ScheduledStep['phase'], string, [Device, number][]][] = [
    [nightOffset('23:00'), 'sleep', '入睡：关灯', [['light', 0]]],
    [nightOffset('01:00'), 'deep', deepAc !== ac ? `深夜：空调调高到 ${deepAc}°C` : `深夜：空调保持 ${ac}°C（已到偏好边界）`, [['ac', deepAc]]],
    [wake - 30, 'wake', '唤醒 1/3：窗帘微开、灯光 20%', [['curtain', Math.max(curtain, 30)], ['light', 20]]],
    [wake - 15, 'wake', `唤醒 2/3：窗帘 60%、灯光 40%、空调回到 ${ac}°C`, [['curtain', Math.max(curtain, 60)], ['light', 40], ['ac', ac]]],
    [wake, 'wake', `唤醒 3/3：窗帘全开、灯光 ${wakeLight}%`, [['curtain', 100], ['light', wakeLight]]],
  ];
  return specs.map(([offsetMin, phase, title, targets]) => ({
    stepId: newId('step'),
    phase,
    at: nightClockLabel(offsetMin),
    offsetMin,
    title,
    actions: targets.map(([device, value]) => ({
      actionId: newId('a'),
      device,
      command: COMMAND[device],
      value,
      label: device === 'light' && value === 0 ? '灯光关闭' : LABEL[device](value),
    })),
    status: 'pending',
    executedAt: null,
    source: 'frontend_mock',
  }));
}

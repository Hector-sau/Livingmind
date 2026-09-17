// Front-end mock seed. Mirrors backend/app/demo/seed.py (see docs/test-data.md).
import type { DemoAccount, Person, RestPreference, Scene, Space, SpaceRule } from '../types';

export const MOCK_ACCOUNT: DemoAccount = {
  accountId: 'demo-account',
  displayName: '演示家庭',
  isDemo: true,
};

const SPACE_DEFAULT: RestPreference = { lightBrightness: 30, acTargetTempC: 25, curtainOpenPercent: 0 };

export const GUEST_PERSON_ID = 'person-guest';

export const MOCK_PERSONS: Person[] = [
  {
    personId: 'person-lin',
    name: '林悦',
    description: '设计师，夜里怕亮，喜欢暗一点、偏暖的休息环境',
    restPreference: { lightBrightness: 15, acTargetTempC: 25, curtainOpenPercent: 0 },
    isGuest: false,
    hasPin: true,
    avatarColor: '#4469F0',
  },
  {
    personId: 'person-chen',
    name: '陈川',
    description: '工程师，怕热，习惯留一点窗帘缝透气',
    restPreference: { lightBrightness: 30, acTargetTempC: 22, curtainOpenPercent: 10 },
    isGuest: false,
    hasPin: true,
    avatarColor: '#24A67A',
  },
  {
    personId: 'person-zhou',
    name: '周禾',
    description: '早睡早起，喜欢保留一点自然光，室温偏暖',
    restPreference: { lightBrightness: 20, acTargetTempC: 26.5, curtainOpenPercent: 25 },
    isGuest: false,
    hasPin: true,
    avatarColor: '#B7791F',
  },
  {
    personId: GUEST_PERSON_ID,
    name: '访客',
    description: '未选择个人账号：使用空间默认设置，不读取任何个人偏好',
    restPreference: SPACE_DEFAULT,
    isGuest: true,
    hasPin: false,
    avatarColor: '#66738A',
  },
];

// Demo-only PINs (mirror of the backend). Not authentication.
export const MOCK_PINS: Record<string, string> = { 'person-lin': '2468', 'person-chen': '1357', 'person-zhou': '8024' };

export const MOCK_SPACES: Space[] = [
  { spaceId: 'space-home-bedroom', name: '家 · 主卧', defaultRestPreference: SPACE_DEFAULT, energyMode: 'comfort_first' },
];

export const NIGHT_LIGHT_MAX = 60;

export const MOCK_SPACE_RULES: SpaceRule[] = [
  { ruleId: 'rule-night-light', text: `休息时灯光不超过 ${NIGHT_LIGHT_MAX}%`, enforced: true },
  { ruleId: 'rule-guest-privacy', text: '访客模式不读取任何个人偏好', enforced: true },
  { ruleId: 'rule-confirm', text: '所有设备动作都要先确认再执行（整晚安排随休息计划一起确认；模拟事件的自动调整除外）', enforced: true },
];

export const MOCK_INITIAL_DEVICES = { lightBrightness: 80, acTargetTempC: 26, curtainOpenPercent: 100 };

export const MOCK_SCENES: Scene[] = [
  {
    sceneId: 'scene-rest',
    title: '我想休息',
    description: '一句话生成休息计划，确认后调整灯光、空调和窗帘',
    status: 'implemented',
    verification: '后端与前端测试、网页端到端验证；真机未验证',
    trigger: '用户表达',
  },
  {
    sceneId: 'scene-room-temp',
    title: '室温变化后自动调整',
    description: '休息服务运行中，室温偏离设定时自动调整空调，有冷却时间和次数上限',
    status: 'implemented',
    verification: '后端与前端测试、网页端到端验证（模拟事件，无真实传感器）；真机未验证',
    trigger: '环境事件（模拟）',
  },
  {
    sceneId: 'scene-wake',
    title: '起床渐进唤醒',
    description: '确认休息计划后按整晚安排运行：入睡关灯、深夜微调空调，07:00 前分三步打开窗帘、调亮灯光',
    status: 'implemented',
    verification: '后端与前端测试、网页端到端验证（模拟时钟，由演示按钮推进）；真机未验证',
    trigger: '定时（模拟时钟）',
  },
];

// Overnight schedule (mirror of backend/app/demo/seed.py).
export const NIGHT_START_LOCAL = '22:30';
export const WAKE_TIME_LOCAL = '07:00';
export const DEEP_NIGHT_AC_RAISE_C = 1;
export const WAKE_LIGHT_MAX = 60;

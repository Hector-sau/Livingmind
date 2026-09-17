// Front-end mock seed. Mirrors backend/app/demo/seed.py (see docs/test-data.md).
import type { DemoAccount, OfflineEnergySimulation, Person, RestPreference, Scene, Space, SpaceRule } from '../types';

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

/** Supplied fixed-day evidence. This mirrors the backend's offline data and is never a device-control loop. */
const PV = [0, 0, 0, 0, 0, 0, 0.2, 0.8, 1.8, 3, 4.2, 5, 5.5, 5.2, 4.6, 3.5, 2, 0.8, 0.2, 0, 0, 0, 0, 0];
const WIND = [0.4, 0.4, 0.3, 0.3, 0.2, 0.2, 0.2, 0.3, 0.3, 0.4, 0.3, 0.3, 0.4, 0.4, 0.5, 0.5, 0.4, 0.4, 0.3, 0.3, 0.3, 0.3, 0.3, 0.3];
const LOAD = [0.55, 0.5, 0.45, 0.45, 0.45, 0.55, 0.8, 1.2, 1, 0.85, 0.8, 0.9, 1, 0.9, 0.85, 1, 1.4, 2.2, 2.8, 2.5, 2, 1.5, 1, 0.7];
const PRICE = [0.12, 0.12, 0.12, 0.12, 0.12, 0.12, 0.15, 0.18, 0.18, 0.18, 0.18, 0.18, 0.18, 0.18, 0.18, 0.22, 0.35, 0.45, 0.45, 0.45, 0.35, 0.22, 0.18, 0.15];
const OUTDOOR_F = [66, 65, 64, 64, 63, 64, 66, 69, 73, 77, 81, 85, 88, 90, 91, 90, 87, 83, 79, 75, 72, 70, 68, 67];

export const MOCK_OFFLINE_ENERGY_SIMULATION: OfflineEnergySimulation = {
  source: 'provided_precomputed_offline_simulation',
  scenario: 'Fixed predefined 24-hour household-energy day',
  controller: 'MATD3 framework, single-agent supplied run',
  agentCount: 1,
  resolution: '24 hourly steps',
  metrics: [
    { key: 'daily_cost', label: '日运行成本', unit: 'USD/day', rule: 1.87, matd3: -0.02, lowerIsBetter: true },
    { key: 'grid_import', label: '电网购电', unit: 'kWh/day', rule: 13.61, matd3: 0.76, lowerIsBetter: true },
    { key: 'peak_import', label: '峰值购电', unit: 'kW', rule: 1.95, matd3: 0.37, lowerIsBetter: true },
    { key: 'comfort_violation', label: '舒适违规', unit: 'F*h', rule: 0, matd3: 0, lowerIsBetter: true },
  ],
  assets: [
    { id: 'pv', name: '光伏发电', role: 'supply', control: '只读环境输入' },
    { id: 'wind', name: '风力发电', role: 'supply', control: '只读环境输入' },
    { id: 'base_load', name: '家庭基础负荷', role: 'demand', control: '只读环境输入' },
    { id: 'hvac', name: 'HVAC 空调', role: 'demand', control: '研究动作；App 当前只控制虚拟空调' },
    { id: 'battery', name: '家庭电池', role: 'storage', control: '离线仿真动作，非 App 实时控制' },
    { id: 'grid', name: '电网购售电', role: 'trading', control: '由离线能量平衡计算' },
    { id: 'diesel', name: '柴油备用发电', role: 'backup', control: '离线仿真动作，非 App 实时控制' },
  ],
  profile: PV.map((pvKw, hour) => ({ hour, pvKw, windKw: WIND[hour], baseLoadKw: LOAD[hour], buyPriceUsdPerKwh: PRICE[hour], outdoorTempF: OUTDOOR_F[hour] })),
  limits: [
    '固定预设日；训练和评估使用同一日，结果不外推到其他天气或家庭。',
    'MATD3 框架在本结果中只有一个智能体，不作为多智能体协作证据。',
    '温度为华氏度、成本为美元仿真参数，不是国内家庭实测。',
    '结果为离线仿真，未接入 LivingMind 实时设备或在线能源决策。',
    '旧成本图的总成本包含柴油机成本，但其可见分项未单列柴油机；本数据只展示已确认的最终 KPI。',
  ],
};

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

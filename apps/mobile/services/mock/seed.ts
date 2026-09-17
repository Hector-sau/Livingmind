// Front-end mock seed. Mirrors backend/app/demo/seed.py so both modes tell the same story.
import type { DemoAccount, Person, Space } from '../types';

export const MOCK_ACCOUNT: DemoAccount = {
  accountId: 'demo-account',
  displayName: '演示账户',
  isDemo: true,
};

export const MOCK_PERSONS: Person[] = [
  {
    personId: 'person-lin',
    name: '林悦',
    description: '喜欢暗一点、偏暖的休息环境',
    restPreference: { lightBrightness: 15, acTargetTempC: 25, curtainOpenPercent: 0 },
  },
  {
    personId: 'person-chen',
    name: '陈川',
    description: '怕热，习惯留一点窗帘缝',
    restPreference: { lightBrightness: 30, acTargetTempC: 22, curtainOpenPercent: 10 },
  },
];

export const MOCK_SPACES: Space[] = [{ spaceId: 'space-home-bedroom', name: '家 · 主卧' }];

export const MOCK_INITIAL_DEVICES = { lightBrightness: 80, acTargetTempC: 26, curtainOpenPercent: 100 };

// Design tokens, aligned with the LivingMind presentation design system (DESIGN.md).
export const colors = {
  ink: '#142036',
  muted: '#66738A',
  blue: '#4469F0',
  violet: '#7C5CE5',
  green: '#24A67A',
  amber: '#B7791F',
  red: '#C8414B',
  surface: '#F6F8FC',
  card: '#FFFFFF',
  border: '#E1E6F0',
  homeTint: '#EEF3FF',
  amberTint: '#FBF3E4',
  redTint: '#FCEBEC',
  greenTint: '#E7F6F0',
  navy: '#111C33',
} as const;

export const space = { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, xxl: 32 } as const;

export const radius = { sm: 8, md: 12, lg: 16, pill: 999 } as const;

export const font = {
  title: 26,
  section: 18,
  body: 15,
  small: 13,
  caption: 12,
} as const;

// Width at which the layout switches to two columns (tablet / landscape).
export const SPLIT_BREAKPOINT = 768;

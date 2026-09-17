// Design tokens: bright, clean, sky-blue. Brand accents come from the LivingMind logo
// (teal #18C7C8, green #55C97A, solar yellow #F6C453, wordmark #176B87).
export const colors = {
  ink: '#0F2A3D',
  muted: '#5B7185',
  faint: '#94A8B8',
  blue: '#0284C7', // primary (sky-600): readable with white text
  sky: '#0EA5E9',
  skyLight: '#38BDF8',
  teal: '#18C7C8',
  brandInk: '#176B87',
  violet: '#6366F1',
  green: '#16A34A',
  amber: '#B7791F',
  sun: '#F6C453',
  red: '#E5484D',
  surface: '#F3FAFF',
  card: '#FFFFFF',
  border: '#E3EEF7',
  homeTint: '#E0F2FE',
  skyMist: '#F0F9FF',
  violetTint: '#EEF0FF',
  amberTint: '#FEF6E4',
  redTint: '#FDECEC',
  greenTint: '#E7F8EE',
  tealTint: '#E3FAFA',
  navy: '#0B3A53',
} as const;

export const gradients = {
  sky: ['#38BDF8', '#0284C7'] as const,
  page: ['#EAF6FF', '#F7FBFF'] as const,
  running: ['#E7F8EE', '#E0F2FE'] as const,
  hero: ['#E0F2FE', '#F0F9FF'] as const,
};

export const space = { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, xxl: 32 } as const;

export const radius = { sm: 10, md: 14, lg: 20, pill: 999 } as const;

export const font = {
  title: 26,
  section: 17,
  body: 15,
  small: 13,
  caption: 12,
} as const;

export const shadow = {
  card: { boxShadow: '0px 6px 20px rgba(2, 132, 199, 0.08)' },
  raised: { boxShadow: '0px 10px 28px rgba(2, 132, 199, 0.16)' },
} as const;

// Width at which the layout switches to two columns (tablet / landscape).
export const SPLIT_BREAKPOINT = 768;

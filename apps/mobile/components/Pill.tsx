import { StyleSheet, Text, View } from 'react-native';

import { colors, font, radius, space } from '../theme/tokens';

export type PillTone = 'blue' | 'green' | 'amber' | 'red' | 'muted' | 'violet' | 'teal';

const TONES: Record<PillTone, { bg: string; fg: string }> = {
  blue: { bg: colors.homeTint, fg: colors.blue },
  green: { bg: colors.greenTint, fg: colors.green },
  amber: { bg: colors.amberTint, fg: colors.amber },
  red: { bg: colors.redTint, fg: colors.red },
  muted: { bg: '#EEF3F7', fg: colors.muted },
  violet: { bg: colors.violetTint, fg: colors.violet },
  teal: { bg: colors.tealTint, fg: '#0E8C8D' },
};

export function Pill({ label, tone = 'muted', testID }: { label: string; tone?: PillTone; testID?: string }) {
  const t = TONES[tone];
  return (
    <View style={[styles.pill, { backgroundColor: t.bg }]} testID={testID}>
      <View style={[styles.dot, { backgroundColor: t.fg }]} />
      <Text style={[styles.text, { color: t.fg }]}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  pill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: space.sm + 2,
    paddingVertical: 4,
    borderRadius: radius.pill,
    alignSelf: 'flex-start',
  },
  dot: { width: 6, height: 6, borderRadius: 3 },
  text: { fontSize: font.caption, fontWeight: '700' },
});

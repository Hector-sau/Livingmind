import { StyleSheet, Text, View } from 'react-native';

import { colors, font, radius, space } from '../theme/tokens';

export type PillTone = 'blue' | 'green' | 'amber' | 'red' | 'muted' | 'violet';

const TONES: Record<PillTone, { bg: string; fg: string }> = {
  blue: { bg: colors.homeTint, fg: colors.blue },
  green: { bg: colors.greenTint, fg: colors.green },
  amber: { bg: colors.amberTint, fg: colors.amber },
  red: { bg: colors.redTint, fg: colors.red },
  muted: { bg: colors.surface, fg: colors.muted },
  violet: { bg: '#F4F0FF', fg: colors.violet },
};

export function Pill({ label, tone = 'muted' }: { label: string; tone?: PillTone }) {
  const t = TONES[tone];
  return (
    <View style={[styles.pill, { backgroundColor: t.bg }]}>
      <Text style={[styles.text, { color: t.fg }]}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  pill: { paddingHorizontal: space.sm + 2, paddingVertical: 3, borderRadius: radius.pill, alignSelf: 'flex-start' },
  text: { fontSize: font.caption, fontWeight: '600' },
});

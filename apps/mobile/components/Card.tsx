import type { ReactNode } from 'react';
import { StyleSheet, Text, View, type ViewStyle } from 'react-native';

import { colors, font, radius, space } from '../theme/tokens';

interface Props {
  title?: string;
  right?: ReactNode;
  children: ReactNode;
  style?: ViewStyle;
}

export function Card({ title, right, children, style }: Props) {
  return (
    <View style={[styles.card, style]}>
      {title ? (
        <View style={styles.header}>
          <Text style={styles.title}>{title}</Text>
          {right}
        </View>
      ) : null}
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.card,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.border,
    padding: space.lg,
    gap: space.md,
  },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: space.sm },
  title: { fontSize: font.section, fontWeight: '700', color: colors.ink, flexShrink: 1 },
});

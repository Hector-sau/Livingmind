import type { ReactNode } from 'react';
import { StyleSheet, Text, View, type ViewStyle } from 'react-native';

import { colors, font, radius, shadow, space } from '../theme/tokens';
import { Icon, type IconName } from './Icon';

interface Props {
  title?: string;
  icon?: IconName;
  right?: ReactNode;
  children: ReactNode;
  style?: ViewStyle;
}

export function Card({ title, icon, right, children, style }: Props) {
  return (
    <View style={[styles.card, style]}>
      {title ? (
        <View style={styles.header}>
          <View style={styles.titleRow}>
            {icon ? (
              <View style={styles.iconWrap}>
                <Icon name={icon} size={16} color={colors.blue} />
              </View>
            ) : null}
            <Text style={styles.title}>{title}</Text>
          </View>
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
    borderColor: '#EDF4FA',
    padding: space.lg + 2,
    gap: space.md,
    ...shadow.card,
  },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: space.sm },
  titleRow: { flexDirection: 'row', alignItems: 'center', gap: space.sm, flexShrink: 1 },
  iconWrap: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: colors.homeTint,
    alignItems: 'center',
    justifyContent: 'center',
  },
  title: { fontSize: font.section, fontWeight: '700', color: colors.ink, flexShrink: 1 },
});

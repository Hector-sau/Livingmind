import type { ReactNode } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { colors, font, space } from '../theme/tokens';
import { Icon, type IconName } from './Icon';

interface Props {
  icon: IconName;
  title: string;
  hint?: string;
  compact?: boolean;
  testID?: string;
  children?: ReactNode;
}

/** Friendly empty state: a large soft icon instead of a bare "暂无" line. */
export function EmptyState({ icon, title, hint, compact, testID, children }: Props) {
  const size = compact ? 52 : 76;
  return (
    <View style={[styles.wrap, compact && styles.compact]} testID={testID}>
      <View style={[styles.halo, { width: size + 20, height: size + 20, borderRadius: (size + 20) / 2 }]}>
        <View style={[styles.circle, { width: size, height: size, borderRadius: size / 2 }]}>
          <Icon name={icon} size={compact ? 24 : 34} color={colors.sky} />
        </View>
      </View>
      <Text style={styles.title}>{title}</Text>
      {hint ? <Text style={styles.hint}>{hint}</Text> : null}
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { alignItems: 'center', gap: space.sm, paddingVertical: space.lg },
  compact: { paddingVertical: space.sm },
  halo: { backgroundColor: colors.skyMist, alignItems: 'center', justifyContent: 'center' },
  circle: { backgroundColor: colors.homeTint, alignItems: 'center', justifyContent: 'center' },
  title: { fontSize: font.body, fontWeight: '700', color: colors.ink, textAlign: 'center' },
  hint: { fontSize: font.small, color: colors.muted, textAlign: 'center', lineHeight: 19, maxWidth: 360 },
});

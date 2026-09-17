import { LinearGradient } from 'expo-linear-gradient';
import { useRef } from 'react';
import { ActivityIndicator, Animated, Pressable, StyleSheet, Text, View } from 'react-native';

import { colors, font, gradients, radius, space } from '../theme/tokens';
import { Icon, type IconName } from './Icon';
import { NATIVE_DRIVER } from './motion';

type Variant = 'primary' | 'secondary' | 'danger' | 'ghost';

interface Props {
  label: string;
  onPress: () => void;
  variant?: Variant;
  disabled?: boolean;
  loading?: boolean;
  testID?: string;
  icon?: IconName;
  /** Show only the icon (label is still used for accessibility). */
  iconOnly?: boolean;
  compact?: boolean;
}

const FG: Record<Variant, string> = {
  primary: '#FFFFFF',
  secondary: colors.blue,
  danger: colors.red,
  ghost: colors.blue,
};

export function Button({ label, onPress, variant = 'primary', disabled, loading, testID, icon, iconOnly, compact }: Props) {
  const inactive = disabled || loading;
  const scale = useRef(new Animated.Value(1)).current;
  const to = (v: number) => Animated.spring(scale, { toValue: v, useNativeDriver: NATIVE_DRIVER, speed: 40, bounciness: 6 }).start();
  const fg = FG[variant];
  const height = compact ? 40 : 48;

  const content = (
    <View style={[styles.inner, { minHeight: height }, iconOnly ? { width: height, paddingHorizontal: 0 } : null]}>
      {loading ? (
        <ActivityIndicator color={fg} />
      ) : icon ? (
        <Icon name={icon} size={iconOnly ? 20 : 18} color={fg} />
      ) : null}
      {iconOnly ? null : <Text style={[styles.label, { color: fg }]}>{label}</Text>}
    </View>
  );

  return (
    <Animated.View style={[{ transform: [{ scale }] }, inactive && styles.inactive]}>
      <Pressable
        testID={testID}
        accessibilityRole="button"
        accessibilityLabel={label}
        accessibilityState={{ disabled: !!inactive, busy: !!loading }}
        onPress={onPress}
        onPressIn={() => !inactive && to(0.96)}
        onPressOut={() => to(1)}
        disabled={inactive}
        style={[styles.base, variant !== 'primary' && styles[variant], iconOnly && styles.round]}
      >
        {variant === 'primary' ? (
          <LinearGradient
            colors={[...gradients.sky]}
            start={{ x: 0, y: 0 }}
            end={{ x: 1, y: 1 }}
            style={[styles.gradient, iconOnly && styles.round]}
          >
            {content}
          </LinearGradient>
        ) : (
          content
        )}
      </Pressable>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  base: { borderRadius: radius.pill, overflow: 'hidden', flexShrink: 0 },
  gradient: { borderRadius: radius.pill },
  round: { borderRadius: 999 },
  inner: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: space.sm,
    paddingHorizontal: space.xl,
  },
  secondary: { backgroundColor: colors.card, borderWidth: 1, borderColor: '#BAE6FD' },
  danger: { backgroundColor: colors.card, borderWidth: 1, borderColor: '#F7B9BB' },
  ghost: { backgroundColor: colors.homeTint },
  inactive: { opacity: 0.45 },
  label: { fontSize: font.body, fontWeight: '700', flexShrink: 0 },
});

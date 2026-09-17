import { StyleSheet, Text, View } from 'react-native';

import { colors, font, radius, space } from '../theme/tokens';
import { Button } from './Button';
import { Icon, type IconName } from './Icon';
import { FadeIn } from './motion';

type Tone = 'info' | 'warning' | 'error';

const TONES: Record<Tone, { bg: string; fg: string; icon: IconName }> = {
  info: { bg: colors.homeTint, fg: colors.blue, icon: 'information-circle-outline' },
  warning: { bg: colors.amberTint, fg: colors.amber, icon: 'cloud-offline-outline' },
  error: { bg: colors.redTint, fg: colors.red, icon: 'alert-circle-outline' },
};

interface Props {
  tone: Tone;
  message: string;
  actionLabel?: string;
  onAction?: () => void;
  onDismiss?: () => void;
}

export function Notice({ tone, message, actionLabel, onAction, onDismiss }: Props) {
  const t = TONES[tone];
  return (
    <FadeIn>
      <View accessibilityRole="alert" style={[styles.box, { backgroundColor: t.bg }]}>
        <Icon name={t.icon} size={20} color={t.fg} />
        <Text style={[styles.text, { color: t.fg }]}>{message}</Text>
        <View style={styles.actions}>
          {actionLabel && onAction ? <Button label={actionLabel} variant="secondary" compact onPress={onAction} /> : null}
          {onDismiss ? <Button label="知道了" variant="ghost" compact onPress={onDismiss} /> : null}
        </View>
      </View>
    </FadeIn>
  );
}

const styles = StyleSheet.create({
  box: {
    borderRadius: radius.md,
    paddingHorizontal: space.md,
    paddingVertical: space.sm,
    gap: space.sm,
    flexDirection: 'row',
    alignItems: 'center',
    flexWrap: 'wrap',
  },
  text: { fontSize: font.small, fontWeight: '600', flex: 1, minWidth: 160 },
  actions: { flexDirection: 'row', gap: space.sm },
});

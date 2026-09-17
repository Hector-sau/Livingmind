import { StyleSheet, Text, View } from 'react-native';

import { colors, font, radius, space } from '../theme/tokens';
import { Button } from './Button';

type Tone = 'info' | 'warning' | 'error';

const TONES: Record<Tone, { bg: string; fg: string }> = {
  info: { bg: colors.homeTint, fg: colors.blue },
  warning: { bg: colors.amberTint, fg: colors.amber },
  error: { bg: colors.redTint, fg: colors.red },
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
    <View accessibilityRole="alert" style={[styles.box, { backgroundColor: t.bg }]}>
      <Text style={[styles.text, { color: t.fg }]}>{message}</Text>
      <View style={styles.actions}>
        {actionLabel && onAction ? <Button label={actionLabel} variant="secondary" onPress={onAction} /> : null}
        {onDismiss ? <Button label="知道了" variant="secondary" onPress={onDismiss} /> : null}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  box: { borderRadius: radius.md, padding: space.md, gap: space.sm },
  text: { fontSize: font.body, fontWeight: '500' },
  actions: { flexDirection: 'row', gap: space.sm, flexWrap: 'wrap' },
});

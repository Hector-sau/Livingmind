import { useEffect, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { Icon } from '../../components/Icon';
import { FadeIn } from '../../components/motion';
import type { UndoWindow } from '../../services/types';
import { colors, font, radius, space } from '../../theme/tokens';
import { formatValue, undoSecondsLeft } from './control';

/** Keep in step with LIVINGMIND_UNDO_WINDOW_S on the backend; only drives the bar's width. */
const UNDO_WINDOW_SECONDS = 5;

interface Props {
  window: UndoWindow | null;
  busy: boolean;
  onUndo: () => void;
  onExpire: () => void;
}

/**
 * The safety net that replaces a confirmation dialog.
 *
 * The countdown is visible on purpose: a chance the person cannot see slipping away is
 * not a chance they can use. Saying where undo lands ("回到 80%") matters too — undo is
 * a reverse write of the recorded value, not a guessed opposite.
 */
export function UndoBar({ window, busy, onUndo, onExpire }: Props) {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (!window) return;
    setNow(Date.now());
    const timer = setInterval(() => setNow(Date.now()), 250);
    return () => clearInterval(timer);
  }, [window]);

  const left = window ? undoSecondsLeft(window.expiresAt, now) : 0;

  useEffect(() => {
    if (window && left <= 0) onExpire();
  }, [window, left, onExpire]);

  if (!window || left <= 0) return null;

  const ratio = Math.min(1, Math.max(0, left / UNDO_WINDOW_SECONDS));

  return (
    <FadeIn>
      <View style={styles.bar} testID="undo-bar">
        <View style={styles.row}>
          <View style={styles.check}>
            <Icon name="checkmark" size={18} color={colors.card} />
          </View>
          <View style={styles.text}>
            <Text style={styles.title} numberOfLines={1}>
              {window.label}
            </Text>
            <Text style={styles.sub}>
              撤销将回到 {formatValue(window.device, window.previousValue)}
            </Text>
          </View>
          <Pressable
            onPress={onUndo}
            disabled={busy}
            accessibilityRole="button"
            accessibilityLabel={`撤销，还剩 ${left} 秒`}
            testID="undo-button"
            style={({ pressed }) => [styles.button, (pressed || busy) && styles.buttonPressed]}
          >
            <Icon name="arrow-undo-outline" size={17} color={colors.navy} />
            <Text style={styles.buttonText}>撤销</Text>
            <Text style={styles.count} testID="undo-count">
              {left}
            </Text>
          </Pressable>
        </View>
        <View style={styles.track}>
          <View style={[styles.progress, { width: `${ratio * 100}%` }]} />
        </View>
      </View>
    </FadeIn>
  );
}

const styles = StyleSheet.create({
  bar: {
    backgroundColor: colors.navy,
    borderRadius: radius.lg,
    padding: space.md,
    gap: space.sm,
    boxShadow: '0px 10px 28px rgba(11, 58, 83, 0.28)',
  },
  row: { flexDirection: 'row', alignItems: 'center', gap: space.md },
  check: {
    width: 34,
    height: 34,
    borderRadius: 17,
    backgroundColor: 'rgba(255,255,255,0.16)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  text: { flex: 1, minWidth: 0 },
  title: { fontSize: font.body, fontWeight: '800', color: colors.card },
  sub: { fontSize: font.caption, color: '#B9D7E7', marginTop: 2 },
  button: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 7,
    height: 42,
    paddingHorizontal: space.lg,
    borderRadius: radius.md,
    backgroundColor: colors.card,
  },
  buttonPressed: { opacity: 0.75 },
  buttonText: { fontSize: font.body, fontWeight: '800', color: colors.navy },
  count: { fontSize: font.body, fontWeight: '800', color: colors.navy, minWidth: 14, textAlign: 'center' },
  track: { height: 4, borderRadius: 2, backgroundColor: 'rgba(255,255,255,0.18)', overflow: 'hidden' },
  progress: { height: '100%', borderRadius: 2, backgroundColor: colors.skyLight },
});

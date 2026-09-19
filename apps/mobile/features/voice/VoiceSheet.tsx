import { useEffect, useRef, useState } from 'react';
import { Animated, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import { Icon } from '../../components/Icon';
import { NATIVE_DRIVER, useReducedMotion } from '../../components/motion';
import { colors, font, radius, space } from '../../theme/tokens';
import { captureElapsed, errorMessage, statusLabel, type VoiceMachine } from './machine';

interface Props {
  state: VoiceMachine;
  asrConnected: boolean;
  /** Suggestions offered when there is no recogniser to produce a transcript. */
  examples: readonly string[];
  onExample: (text: string) => void;
  onCancel: () => void;
  onSkipSpeech: () => void;
}

function elapsedLabel(ms: number): string {
  const total = Math.floor(ms / 1000);
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, '0')}`;
}

/** Breathing ring. Scale and opacity only, so it runs on the native driver. */
function Breath({ active }: { active: boolean }) {
  const value = useRef(new Animated.Value(0)).current;
  const reduced = useReducedMotion();
  useEffect(() => {
    if (!active || reduced) {
      value.setValue(0);
      return;
    }
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(value, { toValue: 1, duration: 900, useNativeDriver: NATIVE_DRIVER }),
        Animated.timing(value, { toValue: 0, duration: 900, useNativeDriver: NATIVE_DRIVER }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [active, reduced, value]);
  const scale = value.interpolate({ inputRange: [0, 1], outputRange: [1, 1.18] });
  const opacity = value.interpolate({ inputRange: [0, 1], outputRange: [0.35, 0.75] });
  return <Animated.View style={[styles.breath, { transform: [{ scale }], opacity }]} />;
}

/**
 * Levels are real microphone data, so the waveform is only drawn when a real recogniser
 * is feeding it. Everywhere else "bars are moving" would be decoration that looks exactly
 * like evidence — the one thing this screen must not do.
 */
function Waveform({ levels }: { levels: readonly number[] }) {
  return (
    <View style={styles.wave}>
      {levels.map((level, i) => (
        <View
          key={i}
          style={[
            styles.bar,
            { height: `${Math.max(6, Math.round(level * 100))}%`, backgroundColor: level > 0.5 ? colors.blue : colors.skyLight },
          ]}
        />
      ))}
    </View>
  );
}

export function VoiceSheet({ state, asrConnected, examples, onExample, onCancel, onSkipSpeech }: Props) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (state.status !== 'listening') return;
    const timer = setInterval(() => setNow(Date.now()), 250);
    return () => clearInterval(timer);
  }, [state.status]);

  if (state.status === 'idle') return null;

  const listening = state.status === 'listening' || state.status === 'armed';
  const failed = state.status === 'failed';
  // Without a recogniser, capture ends in a choice rather than a transcript.
  const needsChoice = !asrConnected && (state.status === 'resolving' || listening);

  return (
    <View style={[styles.sheet, failed && styles.sheetFailed]} testID="voice-sheet">
      <View style={styles.row}>
        <View style={styles.orbWrap}>
          {listening ? <Breath active /> : null}
          <View style={[styles.orb, failed && styles.orbFailed]}>
            <Icon name={failed ? 'mic-off-outline' : 'mic-outline'} size={26} color={colors.card} />
          </View>
        </View>

        <View style={styles.body}>
          <View style={styles.titleRow}>
            <Text style={styles.title} testID="voice-status">
              {failed ? errorMessage(state.error) : statusLabel(state.status, asrConnected)}
            </Text>
            {state.status === 'listening' ? (
              <Text style={styles.elapsed} testID="voice-elapsed">
                {elapsedLabel(captureElapsed(state, now))}
              </Text>
            ) : null}
          </View>

          {asrConnected && listening && state.levels.length > 0 ? <Waveform levels={state.levels} /> : null}

          {needsChoice ? (
            <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.examples}>
              {examples.map((text) => (
                <Pressable
                  key={text}
                  onPress={() => onExample(text)}
                  accessibilityRole="button"
                  testID={`voice-example-${text}`}
                  style={({ pressed }) => [styles.example, pressed && styles.examplePressed]}
                >
                  <Text style={styles.exampleText}>{text}</Text>
                </Pressable>
              ))}
            </ScrollView>
          ) : null}
        </View>

        {state.status === 'speaking' ? (
          <Pressable onPress={onSkipSpeech} accessibilityRole="button" testID="voice-skip" style={styles.action}>
            <Text style={styles.actionText}>跳过</Text>
          </Pressable>
        ) : (
          <Pressable onPress={onCancel} accessibilityRole="button" testID="voice-cancel" style={styles.action}>
            <Text style={styles.actionText}>{failed ? '关闭' : '取消'}</Text>
          </Pressable>
        )}
      </View>
    </View>
  );
}

const ORB = 64;

const styles = StyleSheet.create({
  sheet: {
    marginHorizontal: space.md,
    marginBottom: space.md,
    backgroundColor: colors.card,
    borderWidth: 1,
    borderColor: '#BAE0F7',
    borderRadius: radius.lg,
    padding: space.lg,
    boxShadow: '0px 12px 34px rgba(2, 132, 199, 0.18)',
  },
  sheetFailed: { borderColor: '#F3C9CB' },
  row: { flexDirection: 'row', alignItems: 'center', gap: space.lg },
  orbWrap: { width: ORB + 16, height: ORB + 16, alignItems: 'center', justifyContent: 'center' },
  breath: { position: 'absolute', width: ORB + 16, height: ORB + 16, borderRadius: (ORB + 16) / 2, backgroundColor: '#AEDCF6' },
  orb: { width: ORB, height: ORB, borderRadius: ORB / 2, backgroundColor: colors.blue, alignItems: 'center', justifyContent: 'center' },
  orbFailed: { backgroundColor: colors.red },
  body: { flex: 1, minWidth: 0, gap: space.sm },
  titleRow: { flexDirection: 'row', alignItems: 'baseline', gap: space.sm },
  title: { flex: 1, fontSize: font.section + 2, fontWeight: '800', color: colors.ink, letterSpacing: -0.3 },
  elapsed: { fontSize: font.body, color: colors.muted },
  wave: { height: 48, flexDirection: 'row', alignItems: 'center', gap: 3 },
  bar: { width: 5, borderRadius: 3 },
  examples: { flexDirection: 'row', gap: space.sm },
  example: {
    paddingHorizontal: space.md,
    paddingVertical: 8,
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: '#CFE8FA',
    backgroundColor: colors.card,
  },
  examplePressed: { backgroundColor: colors.homeTint },
  exampleText: { fontSize: font.small, color: colors.blue, fontWeight: '600' },
  action: {
    height: 46,
    paddingHorizontal: space.xl,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: 'center',
    justifyContent: 'center',
  },
  actionText: { fontSize: font.body, fontWeight: '700', color: colors.muted },
});

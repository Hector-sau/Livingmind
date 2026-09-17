import { LinearGradient } from 'expo-linear-gradient';
import { useEffect, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Switch, Text, TextInput, View } from 'react-native';

import { Avatar } from '../../components/Avatar';
import { Button } from '../../components/Button';
import { Card } from '../../components/Card';
import { DeviceIcon, Icon, type DeviceKind } from '../../components/Icon';
import { FadeIn } from '../../components/motion';
import { Pill } from '../../components/Pill';
import type { LivingMindApi } from '../../services';
import type { Person, RestPreference } from '../../services/types';
import { colors, font, gradients, radius, shadow, space } from '../../theme/tokens';
import { ActivityList } from '../activity/ActivityList';
import type { RestFlow } from '../rest/useRestFlow';

interface Props {
  api: LivingMindApi;
  flow: RestFlow;
  showEvidence: boolean;
  onToggleEvidence: (v: boolean) => void;
}

interface Stepper {
  device: DeviceKind;
  key: keyof RestPreference;
  label: string;
  unit: string;
  step: number;
  min: number;
  max: number;
}

const STEPPERS: Stepper[] = [
  { device: 'light', key: 'lightBrightness', label: '灯光', unit: '%', step: 5, min: 0, max: 60 },
  { device: 'ac', key: 'acTargetTempC', label: '空调', unit: '°C', step: 0.5, min: 16, max: 30 },
  { device: 'curtain', key: 'curtainOpenPercent', label: '窗帘', unit: '%', step: 5, min: 0, max: 100 },
];

const SHORT = { lightBrightness: 'light', acTargetTempC: 'ac', curtainOpenPercent: 'curtain' } as const;

function PrefTile({
  cfg,
  value,
  editable,
  onChange,
}: {
  cfg: Stepper;
  value: number;
  editable: boolean;
  onChange: (v: number) => void;
}) {
  const clamp = (v: number) => Math.min(cfg.max, Math.max(cfg.min, Math.round(v * 10) / 10));
  return (
    <View style={styles.prefTile}>
      <DeviceIcon device={cfg.device} size={18} color={colors.blue} />
      <Text style={styles.prefLabel}>{cfg.label}</Text>
      <Text style={styles.prefValue} testID={`pref-${SHORT[cfg.key]}-value`}>
        {value}
        {cfg.unit}
      </Text>
      {editable ? (
        <View style={styles.stepRow}>
          <Pressable
            style={styles.stepBtn}
            onPress={() => onChange(clamp(value - cfg.step))}
            accessibilityRole="button"
            accessibilityLabel={`${cfg.label}减少`}
            testID={`pref-${SHORT[cfg.key]}-minus`}
          >
            <Text style={styles.stepText}>−</Text>
          </Pressable>
          <Pressable
            style={styles.stepBtn}
            onPress={() => onChange(clamp(value + cfg.step))}
            accessibilityRole="button"
            accessibilityLabel={`${cfg.label}增加`}
            testID={`pref-${SHORT[cfg.key]}-plus`}
          >
            <Text style={styles.stepText}>＋</Text>
          </Pressable>
        </View>
      ) : null}
    </View>
  );
}

export function MeScreen({ api, flow, showEvidence, onToggleEvidence }: Props) {
  const { state, person, activeService, actions } = flow;
  const [target, setTarget] = useState<Person | null>(null);
  const [pin, setPin] = useState('');
  const [pinError, setPinError] = useState<string | null>(null);
  const persons = state.data?.persons ?? [];
  const locked = !!activeService;

  const choose = async (p: Person) => {
    setPinError(null);
    setPin('');
    if (!p.hasPin) {
      const res = await actions.unlockPerson(p.personId, null);
      if (!res.ok) setPinError(res.error.message);
      setTarget(null);
      return;
    }
    setTarget(p);
  };

  const submitPin = async () => {
    if (!target) return;
    const res = await actions.unlockPerson(target.personId, pin);
    if (res.ok) {
      setTarget(null);
      setPin('');
    } else {
      setPinError(res.error.message);
    }
  };

  const memory = state.memory;
  const [draft, setDraft] = useState<RestPreference | null>(null);
  const [prefError, setPrefError] = useState<string | null>(null);
  useEffect(() => {
    setDraft(memory ? { ...memory.preference } : null);
    setPrefError(null);
  }, [memory]);
  const pref = draft;
  const dirty =
    !!memory &&
    !!draft &&
    (draft.lightBrightness !== memory.preference.lightBrightness ||
      draft.acTargetTempC !== memory.preference.acTargetTempC ||
      draft.curtainOpenPercent !== memory.preference.curtainOpenPercent);
  const save = async () => {
    if (!draft) return;
    const res = await actions.updatePreference(draft);
    setPrefError(res.ok ? null : res.error.message);
  };

  return (
    <ScrollView contentContainerStyle={styles.page}>
      {person && pref ? (
        <FadeIn>
          <LinearGradient colors={[...gradients.hero]} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={styles.hero}>
            <View style={styles.me}>
              <Avatar name={person.name} color={person.avatarColor} size={60} />
              <View style={styles.meText}>
                <Text style={styles.name}>{person.name}</Text>
                <Text style={styles.desc}>{person.description}</Text>
              </View>
              {person.isGuest ? <Pill label="访客" tone="muted" /> : null}
            </View>
            <Text style={styles.section}>{person.isGuest ? '空间默认设置' : '我的休息偏好（只有你自己能看到）'}</Text>
            <View style={styles.prefs}>
              {STEPPERS.map((cfg) => (
                <PrefTile
                  key={cfg.key}
                  cfg={cfg}
                  value={pref[cfg.key]}
                  editable={!!memory?.editable}
                  onChange={(v) => setDraft({ ...pref, [cfg.key]: v })}
                />
              ))}
            </View>
            {prefError ? <Text style={styles.error}>{prefError}</Text> : null}
            {memory?.editable ? (
              <View style={styles.pinActions}>
                <Button
                  label="保存偏好"
                  icon="save-outline"
                  onPress={save}
                  disabled={!dirty}
                  loading={state.busy === 'memory'}
                  testID="pref-save"
                />
                {dirty ? <Button label="还原" variant="ghost" onPress={() => memory && setDraft({ ...memory.preference })} /> : null}
              </View>
            ) : (
              <Text style={styles.hint}>访客使用空间默认设置，不能编辑。</Text>
            )}
            <Text style={styles.hint}>
              {memory?.updatedAt ? '已按你的修改保存（仅本次演示内有效）。' : '预设的演示偏好；修改后下一次计划会使用新偏好。'}
            </Text>
          </LinearGradient>
        </FadeIn>
      ) : null}

      {memory ? (
        <Card title="空间规则（所有人可见）" icon="home-outline">
          {memory.sharedRules.map((r) => (
            <View key={r.ruleId} style={styles.ruleRow}>
              <Icon name={r.enforced ? 'shield-checkmark-outline' : 'information-circle-outline'} size={16} color={colors.blue} />
              <Text style={styles.ruleText}>{r.text}</Text>
              {r.enforced ? <Pill label="代码强制" tone="blue" /> : null}
            </View>
          ))}
        </Card>
      ) : null}

      <Card title="切换使用者" icon="people-outline">
        <Text style={styles.hint}>共享平板上用四位 PIN 防止误切换。这是演示功能，不是登录认证。</Text>
        {locked ? <Text style={styles.warn}>休息服务运行中，停止后才能切换。</Text> : null}
        <View style={styles.people}>
          {persons
            .filter((p) => p.personId !== state.personId)
            .map((p) => (
              <Pressable
                key={p.personId}
                style={[styles.person, locked && styles.disabled]}
                disabled={locked || state.busy !== null}
                onPress={() => choose(p)}
                accessibilityRole="button"
                testID={`person-option-${p.personId}`}
              >
                <Avatar name={p.name} color={p.avatarColor} size={36} />
                <Text style={styles.personName}>{p.isGuest ? '访客模式' : p.name}</Text>
              </Pressable>
            ))}
        </View>
        {target ? (
          <View style={styles.pinBox}>
            <Text style={styles.pinTitle}>输入 {target.name} 的 PIN</Text>
            <TextInput
              value={pin}
              onChangeText={(v) => setPin(v.replace(/\D/g, '').slice(0, 4))}
              keyboardType="number-pad"
              secureTextEntry
              maxLength={4}
              style={styles.pinInput}
              placeholder="••••"
              placeholderTextColor={colors.muted}
              onSubmitEditing={submitPin}
              accessibilityLabel="PIN 输入"
              testID="pin-input"
            />
            {pinError ? (
              <Text style={styles.error} testID="pin-error">
                {pinError}
              </Text>
            ) : null}
            <View style={styles.pinActions}>
              <Button label="确认" icon="lock-open-outline" onPress={submitPin} disabled={pin.length !== 4} loading={state.busy === 'unlock'} testID="pin-submit" />
              <Button label="取消" variant="secondary" onPress={() => setTarget(null)} />
            </View>
            <Text style={styles.hint}>演示 PIN：林悦 2468 · 陈川 1357 · 周禾 8024</Text>
          </View>
        ) : null}
      </Card>

      <Card title="演示与证据" icon="shield-checkmark-outline">
        <View style={styles.switchRow}>
          <View style={styles.switchText}>
            <Text style={styles.body}>证据面板</Text>
            <Text style={styles.hint}>显示原始调用记录（来源、执行结果），给评审和技术讲解用。</Text>
          </View>
          <Switch
            value={showEvidence}
            onValueChange={onToggleEvidence}
            trackColor={{ false: '#D5E3EE', true: colors.skyLight }}
            thumbColor="#FFFFFF"
            testID="evidence-switch"
          />
        </View>
        <Text style={styles.hint}>
          当前连接：{api.mode === 'mock' ? '前端模拟模式（没有后端、没有模型）' : '后端模式'} · 所有设备均为虚拟设备
        </Text>
        <Button label="重置演示数据" icon="refresh-outline" variant="ghost" onPress={actions.resetDemo} loading={state.busy === 'reset'} disabled={state.busy !== null} />
      </Card>

      {showEvidence ? (
        <View testID="evidence-panel">
          <ActivityList items={state.activity} />
        </View>
      ) : null}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  page: { padding: space.lg, gap: space.md, maxWidth: 760, width: '100%', alignSelf: 'center' },
  hero: { borderRadius: radius.lg, padding: space.xl, gap: space.md, ...shadow.card },
  me: { flexDirection: 'row', alignItems: 'center', gap: space.md },
  meText: { flex: 1, gap: 2 },
  name: { fontSize: 22, fontWeight: '700', color: colors.ink },
  desc: { fontSize: font.small, color: colors.muted },
  section: { fontSize: font.small, color: colors.muted, marginTop: space.sm },
  prefs: { flexDirection: 'row', gap: space.sm, flexWrap: 'wrap' },
  prefTile: { flexGrow: 1, flexBasis: 90, backgroundColor: colors.card, borderRadius: radius.md, padding: space.md, gap: 2 },
  prefLabel: { fontSize: font.caption, color: colors.muted, marginTop: 4 },
  prefValue: { fontSize: 20, color: colors.ink, fontWeight: '800' },
  stepRow: { flexDirection: 'row', gap: space.sm, marginTop: space.sm },
  stepBtn: {
    width: 40,
    height: 36,
    borderRadius: 18,
    backgroundColor: colors.homeTint,
    alignItems: 'center',
    justifyContent: 'center',
  },
  stepText: { fontSize: 18, color: colors.blue, fontWeight: '700' },
  ruleRow: { flexDirection: 'row', alignItems: 'center', gap: space.sm },
  ruleText: { flex: 1, fontSize: font.body, color: colors.ink },
  hint: { fontSize: font.caption, color: colors.muted },
  warn: { fontSize: font.small, color: colors.amber, fontWeight: '600' },
  people: { flexDirection: 'row', flexWrap: 'wrap', gap: space.sm },
  person: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.sm,
    paddingLeft: 6,
    paddingRight: space.lg,
    paddingVertical: 6,
    borderRadius: radius.pill,
    backgroundColor: colors.skyMist,
    borderWidth: 1,
    borderColor: '#D6ECFB',
    minHeight: 48,
  },
  disabled: { opacity: 0.45 },
  personName: { fontSize: font.body, color: colors.ink, fontWeight: '600' },
  pinBox: { gap: space.sm, padding: space.lg, borderRadius: radius.md, backgroundColor: colors.skyMist },
  pinTitle: { fontSize: font.body, fontWeight: '600', color: colors.ink },
  pinInput: {
    height: 52,
    borderWidth: 1,
    borderColor: '#BAE6FD',
    borderRadius: radius.md,
    textAlign: 'center',
    fontSize: 24,
    letterSpacing: 12,
    backgroundColor: colors.card,
    color: colors.ink,
  },
  error: { fontSize: font.small, color: colors.red, fontWeight: '600' },
  pinActions: { flexDirection: 'row', gap: space.sm },
  switchRow: { flexDirection: 'row', alignItems: 'center', gap: space.md },
  switchText: { flex: 1, gap: 2 },
  body: { fontSize: font.body, color: colors.ink, fontWeight: '600' },
});

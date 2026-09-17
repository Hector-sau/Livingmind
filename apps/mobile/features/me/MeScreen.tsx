import { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Switch, Text, TextInput, View } from 'react-native';

import { Avatar } from '../../components/Avatar';
import { Button } from '../../components/Button';
import { Card } from '../../components/Card';
import { Pill } from '../../components/Pill';
import type { LivingMindApi } from '../../services';
import type { Person } from '../../services/types';
import { colors, font, radius, space } from '../../theme/tokens';
import { ActivityList } from '../activity/ActivityList';
import type { RestFlow } from '../rest/useRestFlow';

interface Props {
  api: LivingMindApi;
  flow: RestFlow;
  showEvidence: boolean;
  onToggleEvidence: (v: boolean) => void;
}

function PrefRow({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.prefRow}>
      <Text style={styles.prefLabel}>{label}</Text>
      <Text style={styles.prefValue}>{value}</Text>
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

  const pref = person?.restPreference;

  return (
    <ScrollView contentContainerStyle={styles.page}>
      {person && pref ? (
        <Card>
          <View style={styles.me}>
            <Avatar name={person.name} color={person.avatarColor} size={56} />
            <View style={styles.meText}>
              <Text style={styles.name}>{person.name}</Text>
              <Text style={styles.desc}>{person.description}</Text>
            </View>
            {person.isGuest ? <Pill label="访客" tone="muted" /> : null}
          </View>
          <Text style={styles.section}>{person.isGuest ? '空间默认设置' : '我的休息偏好（只有你自己能看到）'}</Text>
          <PrefRow label="灯光" value={`${pref.lightBrightness}%`} />
          <PrefRow label="空调" value={`${pref.acTargetTempC}°C`} />
          <PrefRow label="窗帘" value={`${pref.curtainOpenPercent}%`} />
          <Text style={styles.hint}>偏好是演示用的预设数据，编辑功能在后续步骤。</Text>
        </Card>
      ) : null}

      <Card title="切换使用者">
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
              <Button label="确认" onPress={submitPin} disabled={pin.length !== 4} loading={state.busy === 'unlock'} testID="pin-submit" />
              <Button label="取消" variant="secondary" onPress={() => setTarget(null)} />
            </View>
            <Text style={styles.hint}>演示 PIN：林悦 2468 · 陈川 1357 · 周禾 8024</Text>
          </View>
        ) : null}
      </Card>

      <Card title="演示与证据">
        <View style={styles.switchRow}>
          <View style={styles.switchText}>
            <Text style={styles.body}>证据面板</Text>
            <Text style={styles.hint}>显示原始调用记录（来源、执行结果），给评审和技术讲解用。</Text>
          </View>
          <Switch value={showEvidence} onValueChange={onToggleEvidence} testID="evidence-switch" />
        </View>
        <Text style={styles.hint}>
          当前连接：{api.mode === 'mock' ? '前端模拟模式（没有后端、没有模型）' : '后端模式'} · 所有设备均为虚拟设备
        </Text>
        <Button label="重置演示数据" variant="secondary" onPress={actions.resetDemo} loading={state.busy === 'reset'} disabled={state.busy !== null} />
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
  me: { flexDirection: 'row', alignItems: 'center', gap: space.md },
  meText: { flex: 1, gap: 2 },
  name: { fontSize: 22, fontWeight: '700', color: colors.ink },
  desc: { fontSize: font.small, color: colors.muted },
  section: { fontSize: font.small, color: colors.muted, marginTop: space.sm },
  prefRow: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: space.xs },
  prefLabel: { fontSize: font.body, color: colors.muted },
  prefValue: { fontSize: font.body, color: colors.ink, fontWeight: '600' },
  hint: { fontSize: font.caption, color: colors.muted },
  warn: { fontSize: font.small, color: colors.amber, fontWeight: '600' },
  people: { flexDirection: 'row', flexWrap: 'wrap', gap: space.sm },
  person: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.sm,
    paddingHorizontal: space.md,
    paddingVertical: space.sm,
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: colors.border,
    minHeight: 48,
  },
  disabled: { opacity: 0.45 },
  personName: { fontSize: font.body, color: colors.ink, fontWeight: '600' },
  pinBox: { gap: space.sm, padding: space.md, borderRadius: radius.md, backgroundColor: colors.surface },
  pinTitle: { fontSize: font.body, fontWeight: '600', color: colors.ink },
  pinInput: {
    height: 52,
    borderWidth: 1,
    borderColor: colors.border,
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

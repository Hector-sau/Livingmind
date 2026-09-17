import { Pressable, StyleSheet, Text, View } from 'react-native';

import { Card } from '../../components/Card';
import type { Person } from '../../services/types';
import { colors, font, radius, space } from '../../theme/tokens';

interface Props {
  persons: Person[];
  selectedId: string | null;
  disabled?: boolean;
  onSelect: (personId: string) => void;
}

export function PersonPicker({ persons, selectedId, disabled, onSelect }: Props) {
  return (
    <Card title="谁在使用">
      <Text style={styles.hint}>切换人物只是切换演示上下文，不是登录。</Text>
      <View style={styles.row}>
        {persons.map((p) => {
          const selected = p.personId === selectedId;
          const pref = p.restPreference;
          return (
            <Pressable
              key={p.personId}
              accessibilityRole="radio"
              accessibilityState={{ selected, disabled: !!disabled }}
              disabled={disabled}
              onPress={() => onSelect(p.personId)}
              style={[styles.item, selected && styles.itemSelected, disabled && styles.disabled]}
            >
              <Text style={[styles.name, selected && styles.nameSelected]}>{p.name}</Text>
              <Text style={styles.desc}>{p.description}</Text>
              <Text style={styles.pref}>
                偏好：灯光 {pref.lightBrightness}% · {pref.acTargetTempC}°C · 窗帘 {pref.curtainOpenPercent}%
              </Text>
            </Pressable>
          );
        })}
      </View>
    </Card>
  );
}

const styles = StyleSheet.create({
  hint: { fontSize: font.small, color: colors.muted },
  row: { flexDirection: 'row', flexWrap: 'wrap', gap: space.md },
  item: {
    flexGrow: 1,
    flexBasis: 200,
    borderWidth: 1.5,
    borderColor: colors.border,
    borderRadius: radius.md,
    padding: space.md,
    gap: space.xs,
    minHeight: 48,
  },
  itemSelected: { borderColor: colors.blue, backgroundColor: colors.homeTint },
  disabled: { opacity: 0.5 },
  name: { fontSize: font.section, fontWeight: '700', color: colors.ink },
  nameSelected: { color: colors.blue },
  desc: { fontSize: font.small, color: colors.muted },
  pref: { fontSize: font.caption, color: colors.muted },
});

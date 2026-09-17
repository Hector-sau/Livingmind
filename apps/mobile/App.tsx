import { StatusBar } from 'expo-status-bar';
import { StyleSheet, Text, View } from 'react-native';
import { SafeAreaProvider, SafeAreaView } from 'react-native-safe-area-context';

import { appConfig } from './config';
import { colors, font, space } from './theme/tokens';

export default function App() {
  return (
    <SafeAreaProvider>
      <SafeAreaView style={styles.root}>
        <View style={styles.center}>
          <Text style={styles.title}>LivingMind</Text>
          <Text style={styles.body}>
            {appConfig.mode === 'mock' ? '前端模拟模式' : `后端：${appConfig.apiBaseUrl}`}
          </Text>
        </View>
        <StatusBar style="dark" />
      </SafeAreaView>
    </SafeAreaProvider>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.surface },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: space.sm },
  title: { fontSize: font.title, fontWeight: '700', color: colors.ink },
  body: { fontSize: font.body, color: colors.muted },
});

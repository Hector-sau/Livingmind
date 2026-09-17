import { StatusBar } from 'expo-status-bar';
import { StyleSheet } from 'react-native';
import { SafeAreaProvider, SafeAreaView } from 'react-native-safe-area-context';

import { appConfig } from './config';
import { HomeScreen } from './features/home/HomeScreen';
import { api } from './services';
import { colors } from './theme/tokens';

export default function App() {
  return (
    <SafeAreaProvider>
      <SafeAreaView style={styles.root} edges={['top', 'left', 'right']}>
        <HomeScreen api={api} backendLabel={appConfig.apiBaseUrl} />
        <StatusBar style="dark" />
      </SafeAreaView>
    </SafeAreaProvider>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.card },
});

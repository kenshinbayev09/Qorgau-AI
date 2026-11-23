import { Stack } from 'expo-router';
import { ActivityIndicator, View } from 'react-native';
import { StatusBar } from 'expo-status-bar';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { AppProvider, useApp } from '../state/AppContext';

function RootStack() {
  const { c, isDark, t, ready } = useApp();
  if (!ready) {
    return <View style={{ flex: 1, backgroundColor: c.bg, alignItems: 'center', justifyContent: 'center' }}><ActivityIndicator color={c.teal} /></View>;
  }
  return (
    <>
      <StatusBar style={isDark ? 'light' : 'dark'} />
      <Stack
        screenOptions={{
          headerStyle: { backgroundColor: c.bg },
          headerTintColor: c.text,
          headerShadowVisible: false,
          contentStyle: { backgroundColor: c.bg },
          headerBackTitle: t('common.back'),
        }}
      >
        <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
        <Stack.Screen name="result/[id]" options={{ title: t('result.title') }} />
        <Stack.Screen name="media" options={{ title: t('media.title') }} />
        <Stack.Screen name="scan" options={{ title: t('qr.title') }} />
        <Stack.Screen name="file-scan" options={{ title: t('fileScan.title') }} />
        <Stack.Screen name="learn/[id]" options={{ title: t('learn.title') }} />
        <Stack.Screen name="privacy" options={{ title: t('privacy.title') }} />
      </Stack>
    </>
  );
}

export default function RootLayout() {
  return (
    <SafeAreaProvider>
      <AppProvider>
        <RootStack />
      </AppProvider>
    </SafeAreaProvider>
  );
}

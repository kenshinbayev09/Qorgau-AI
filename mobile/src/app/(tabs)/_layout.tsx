import Ionicons from '@expo/vector-icons/Ionicons';
import { Tabs } from 'expo-router';

import { useApp } from '../../state/AppContext';
import type { IconName } from '../../theme/theme';

const icons: Record<string, [IconName, IconName]> = {
  index: ['home', 'home-outline'],
  check: ['shield-checkmark', 'shield-checkmark-outline'],
  assistant: ['sparkles', 'sparkles-outline'],
  history: ['time', 'time-outline'],
  settings: ['settings', 'settings-outline'],
};

export default function TabLayout() {
  const { c, t } = useApp();
  return (
    <Tabs
      screenOptions={({ route }) => ({
        headerShown: false,
        tabBarActiveTintColor: c.teal,
        tabBarInactiveTintColor: c.textSecondary,
        tabBarStyle: { backgroundColor: c.card, borderTopColor: c.border },
        tabBarLabelStyle: { fontSize: 12, fontWeight: '600' },
        tabBarIcon: ({ color, focused, size }) => (
          <Ionicons name={icons[route.name]?.[focused ? 0 : 1] ?? 'ellipse'} size={size} color={String(color)} />
        ),
      })}
    >
      <Tabs.Screen name="index" options={{ title: t('tabs.welcome') }} />
      <Tabs.Screen name="check" options={{ title: t('tabs.check') }} />
      <Tabs.Screen name="assistant" options={{ title: t('tabs.assistant') }} />
      <Tabs.Screen name="history" options={{ title: t('tabs.history') }} />
      <Tabs.Screen name="settings" options={{ title: t('tabs.settings') }} />
    </Tabs>
  );
}

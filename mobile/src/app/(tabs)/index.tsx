import Ionicons from '@expo/vector-icons/Ionicons';
import { router } from 'expo-router';
import { Pressable, View } from 'react-native';

import { DevicesIllustration } from '../../components/Devices';
import { Card, Screen, T } from '../../components/ui';
import { useApp } from '../../state/AppContext';
import { radius, space, type IconName } from '../../theme/theme';

const ICONS: IconName[] = ['shield-checkmark-outline', 'sparkles-outline', 'time-outline', 'settings-outline'];

export default function Welcome() {
  const { c, t, tl } = useApp();
  const buttons = tl<{ t: string; d: string }[]>('welcome.buttons');

  return (
    <Screen>
      <View style={{ alignItems: 'center', marginTop: space.s }}>
        <DevicesIllustration width={320} />
      </View>

      <View style={{ gap: space.s, marginTop: space.s }}>
        <T v="h1">{t('welcome.title')}</T>
        <T color={c.textSecondary}>{t('welcome.subtitle')}</T>
      </View>

      <T v="label" color={c.textSecondary} style={{ marginTop: space.m, letterSpacing: 1 }}>
        {t('welcome.buttonsTitle').toUpperCase()}
      </T>
      <View style={{ gap: space.s }}>
        {buttons.map((b, i) => (
          <Card key={b.t} style={{ flexDirection: 'row', alignItems: 'center', gap: space.m, borderRadius: radius.m }}>
            <View style={{ width: 40, height: 40, borderRadius: radius.s, backgroundColor: c.cardAlt, alignItems: 'center', justifyContent: 'center' }}>
              <Ionicons name={ICONS[i] ?? 'ellipse-outline'} size={20} color={c.teal} />
            </View>
            <View style={{ flex: 1, gap: 2 }}>
              <T v="label">{b.t}</T>
              <T v="small" color={c.textSecondary}>{b.d}</T>
            </View>
          </Card>
        ))}
      </View>

      <T v="small" color={c.textSecondary} style={{ marginTop: space.s }}>{t('welcome.note')}</T>

      <Pressable onPress={() => router.push('/learn/phishing')} accessibilityRole="link" hitSlop={8} style={{ alignSelf: 'center', marginTop: space.s }}>
        <T v="label" color={c.teal}>{t('learn.title')}</T>
      </Pressable>
    </Screen>
  );
}

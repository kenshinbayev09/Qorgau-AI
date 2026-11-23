import Ionicons from '@expo/vector-icons/Ionicons';
import { useLocalSearchParams } from 'expo-router';
import { View } from 'react-native';

import { Card, EmptyState, FadeIn, Screen, T } from '../../components/ui';
import { useApp } from '../../state/AppContext';
import { space } from '../../theme/theme';

const IDS = ['phishing', 'deepfake', 'after'] as const;

export default function LearnCard() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { c, t, tl } = useApp();
  if (!IDS.includes(id as (typeof IDS)[number])) return <Screen edges={['bottom']}><EmptyState icon="book-outline" title="—" /></Screen>;
  const points = tl<string[]>(`learn.cards.${id}.points`);
  return (
    <Screen edges={['bottom']}>
      <T v="h1">{t(`learn.cards.${id}.title`)}</T>
      <T color={c.textSecondary}>{t(`learn.cards.${id}.short`)}</T>
      {points.map((p, i) => (
        <FadeIn key={i} delay={60 * i}>
          <Card style={{ flexDirection: 'row', gap: space.m, alignItems: 'flex-start' }}>
            <View style={{ width: 28, height: 28, borderRadius: 14, backgroundColor: c.teal + '22', alignItems: 'center', justifyContent: 'center' }}>
              <T v="label" color={c.teal}>{i + 1}</T>
            </View>
            <T style={{ flex: 1 }}>{p}</T>
          </Card>
        </FadeIn>
      ))}
      <Card style={{ flexDirection: 'row', gap: space.s, backgroundColor: c.cardAlt }}>
        <Ionicons name="shield-checkmark" size={20} color={c.green} />
        <T v="small" color={c.textSecondary} style={{ flex: 1 }}>{t('home.tips.2')}</T>
      </Card>
    </Screen>
  );
}

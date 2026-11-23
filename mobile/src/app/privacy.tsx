import Ionicons from '@expo/vector-icons/Ionicons';
import { useEffect, useState } from 'react';
import { View } from 'react-native';

import type { Health } from '../api/types';
import { Card, Screen, T } from '../components/ui';
import { useApp } from '../state/AppContext';
import { space } from '../theme/theme';

export default function Privacy() {
  const { c, t, tl, api } = useApp();
  const [health, setHealth] = useState<Health | null | undefined>(undefined);
  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth(null));
  }, [api]);
  const items = tl<{ t: string; d: string }[]>('privacy.items');
  const onOff = (v: boolean | undefined) => (v === undefined ? t('privacy.unknown') : v ? t('privacy.on') : t('privacy.off'));
  return (
    <Screen edges={['bottom']}>
      {items.map((it, i) => (
        <Card key={i} style={{ flexDirection: 'row', gap: space.m }}>
          <Ionicons name="shield-half" size={22} color={c.teal} />
          <View style={{ flex: 1, gap: 2 }}>
            <T v="label">{it.t}</T>
            <T v="small" color={c.textSecondary}>{it.d}</T>
          </View>
        </Card>
      ))}
      <Card accent={c.blue}>
        <T v="small">
          {t('privacy.externalNow', {
            sb: onOff(health?.external_services.safe_browsing),
            llm: onOff(health?.external_services.llm_explanations),
          })}
        </T>
      </Card>
    </Screen>
  );
}

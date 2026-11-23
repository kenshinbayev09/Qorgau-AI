import Ionicons from '@expo/vector-icons/Ionicons';
import { router, useFocusEffect } from 'expo-router';
import { useCallback, useState } from 'react';
import { Alert, FlatList, TextInput, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { HistoryRow } from '../../components/risk';
import { Chip, EmptyState, T } from '../../components/ui';
import type { HistoryEntry } from '../../db/history';
import { useApp } from '../../state/AppContext';
import { font, radius, riskMeta, space, touch } from '../../theme/theme';

const CATS = ['all', 'high', 'suspicious', 'low', 'insufficient'] as const;
const KINDS = ['all', 'url', 'media'] as const;

export default function HistoryScreen() {
  const { c, t, repo, historyVersion, bumpHistory } = useApp();
  const [query, setQuery] = useState('');
  const [kind, setKind] = useState<(typeof KINDS)[number]>('all');
  const [cat, setCat] = useState<(typeof CATS)[number]>('all');
  const [items, setItems] = useState<HistoryEntry[] | null>(null);
  const [total, setTotal] = useState(0);

  useFocusEffect(
    useCallback(() => {
      repo.list({ query, kind, category: cat }).then(setItems).catch(() => setItems([]));
      repo.list({ limit: 1 }).then((x) => setTotal(x.length)).catch(() => setTotal(0));
    }, [repo, query, kind, cat, historyVersion]),
  );

  const remove = (e: HistoryEntry) =>
    Alert.alert(t('history.deleteConfirm'), e.title, [
      { text: t('common.cancel'), style: 'cancel' },
      { text: t('common.delete'), style: 'destructive', onPress: () => repo.remove(e.id).then(bumpHistory) },
    ]);

  return (
    <SafeAreaView edges={['top']} style={{ flex: 1, backgroundColor: c.bg }}>
      <View style={{ padding: space.m, gap: space.m }}>
        <T v="h1">{t('history.title')}</T>
        <View style={{ flexDirection: 'row', alignItems: 'center', backgroundColor: c.card, borderRadius: radius.m, borderWidth: 1, borderColor: c.border, paddingHorizontal: space.m }}>
          <Ionicons name="search" size={18} color={c.textSecondary} />
          <TextInput value={query} onChangeText={setQuery} placeholder={t('history.search')} placeholderTextColor={c.textSecondary}
            autoCapitalize="none" autoCorrect={false} accessibilityLabel={t('history.search')}
            style={[font.body, { flex: 1, color: c.text, minHeight: touch, paddingHorizontal: space.s }]} />
        </View>
        <View style={{ flexDirection: 'row', gap: space.s, flexWrap: 'wrap' }}>
          {KINDS.map((k) => <Chip key={k} label={t(`history.${k}`)} selected={kind === k} onPress={() => setKind(k)} />)}
        </View>
        <View style={{ flexDirection: 'row', gap: space.s, flexWrap: 'wrap' }}>
          {CATS.map((k) => (
            <Chip key={k} label={k === 'all' ? t('history.all') : t(`risk.${k}`)} selected={cat === k} onPress={() => setCat(k)}
              color={k === 'all' ? undefined : riskMeta(c, k).color} />
          ))}
        </View>
      </View>
      <FlatList
        data={items ?? []}
        keyExtractor={(e) => e.id}
        contentContainerStyle={{ paddingHorizontal: space.m, paddingBottom: space.xxl, gap: space.s }}
        renderItem={({ item }) => <HistoryRow e={item} onPress={() => router.push(`/result/${item.id}`)} onDelete={() => remove(item)} />}
        ListEmptyComponent={
          items === null ? undefined : total === 0 ? (
            <EmptyState icon="file-tray-outline" title={t('history.empty')} hint={t('history.emptyHint')} />
          ) : (
            <EmptyState icon="search-outline" title={t('history.nothingFound')} />
          )
        }
      />
    </SafeAreaView>
  );
}

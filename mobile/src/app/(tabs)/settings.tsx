import Ionicons from '@expo/vector-icons/Ionicons';
import { router } from 'expo-router';
import { useState } from 'react';
import { Alert, Pressable, TextInput, View } from 'react-native';

import { ApiError, errorKey } from '../../api/client';
import type { Health } from '../../api/types';
import { Button, Card, Chip, Screen, SectionTitle, T, ToggleRow } from '../../components/ui';
import { useApp, type LangPref, type ThemePref } from '../../state/AppContext';
import { font, radius, space, touch } from '../../theme/theme';

export default function SettingsScreen() {
  const { c, t, settings, update, api, repo, bumpHistory } = useApp();
  const [apiUrl, setApiUrl] = useState(settings.apiUrl);
  const [health, setHealth] = useState<Health | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [checking, setChecking] = useState(false);

  const test = async () => {
    update('apiUrl', apiUrl.trim());
    setChecking(true);
    setStatus(null);
    try {
      const { QorgauApi } = await import('../../api/client');
      const h = await new QorgauApi(apiUrl.trim()).health();
      setHealth(h);
      setStatus(t('settings.online'));
    } catch (e) {
      setHealth(null);
      setStatus(`${t('settings.offline')}: ${t(`errors.${errorKey(e instanceof ApiError ? e.code : 'network')}`)}`);
    } finally {
      setChecking(false);
    }
  };

  const modelStatus = (s: string | undefined) =>
    ({ loaded: t('settings.statusLoaded'), missing: t('settings.statusMissing'), not_connected: t('settings.statusNotConnected'),
      configured: t('settings.statusConfigured'), error: t('settings.statusError') } as Record<string, string>)[s ?? ''] ?? '—';

  const clearHistory = () =>
    Alert.alert(t('settings.deleteHistory'), t('settings.deleteHistoryConfirm'), [
      { text: t('common.cancel'), style: 'cancel' },
      { text: t('common.delete'), style: 'destructive', onPress: () => repo.clear().then(() => { bumpHistory(); Alert.alert(t('settings.historyDeleted')); }) },
    ]);

  void api;
  return (
    <Screen>
      <T v="h1">{t('settings.title')}</T>

      <SectionTitle>{t('settings.appearance')}</SectionTitle>
      <Card>
        <T v="label" color={c.textSecondary}>{t('settings.theme')}</T>
        <View style={{ flexDirection: 'row', gap: space.s, flexWrap: 'wrap' }}>
          {(['system', 'dark', 'light'] as ThemePref[]).map((k) => (
            <Chip key={k} label={t(`settings.theme${k[0].toUpperCase() + k.slice(1)}`)} selected={settings.theme === k} onPress={() => update('theme', k)} />
          ))}
        </View>
        <T v="label" color={c.textSecondary} style={{ marginTop: space.s }}>{t('settings.language')}</T>
        <View style={{ flexDirection: 'row', gap: space.s, flexWrap: 'wrap' }}>
          {([['system', t('settings.langSystem')], ['ru', 'Русский'], ['kk', 'Қазақша'], ['en', 'English']] as [LangPref, string][]).map(([k, label]) => (
            <Chip key={k} label={label} selected={settings.lang === k} onPress={() => update('lang', k)} />
          ))}
        </View>
      </Card>

      <SectionTitle>{t('settings.server')}</SectionTitle>
      <Card style={{ gap: space.m }}>
        <T v="label" color={c.textSecondary}>{t('settings.serverUrl')}</T>
        <TextInput value={apiUrl} onChangeText={setApiUrl} autoCapitalize="none" autoCorrect={false} keyboardType="url"
          accessibilityLabel={t('settings.serverUrl')}
          style={[font.body, { color: c.text, backgroundColor: c.cardAlt, borderRadius: radius.m, minHeight: touch, paddingHorizontal: space.m }]} />
        <Button title={t('settings.checkServer')} icon="pulse" variant="secondary" onPress={test} loading={checking} />
        {status ? <T v="small" color={health ? c.green : c.red}>{status}</T> : null}
        {health ? (
          <View style={{ gap: 4 }}>
            <T v="small">{t('settings.urlModel')}: {modelStatus(health.url_model.status)} {health.url_model.version ? `(${health.url_model.version})` : ''}</T>
            <T v="small">{t('settings.deepfakeModel')}: {modelStatus(health.deepfake_model.status)} {health.deepfake_model.version ? `(${health.deepfake_model.version})` : ''}</T>
          </View>
        ) : null}
        <ToggleRow label={t('settings.networkChecks')} value={settings.networkChecks} onChange={(v) => update('networkChecks', v)} />
        <ToggleRow label={t('settings.demoMode')} hint={t('settings.demoHint')} value={settings.demoMode} onChange={(v) => update('demoMode', v)} />
      </Card>

      <SectionTitle>{t('settings.privacy')}</SectionTitle>
      <Card style={{ gap: space.s }}>
        <Pressable onPress={() => router.push('/privacy')} accessibilityRole="button" style={{ flexDirection: 'row', alignItems: 'center', gap: space.s, minHeight: touch }}>
          <Ionicons name="lock-closed" size={20} color={c.teal} />
          <T style={{ flex: 1 }}>{t('settings.privacyOpen')}</T>
          <Ionicons name="chevron-forward" size={20} color={c.textSecondary} />
        </Pressable>
        <Button title={t('settings.resetConsent')} variant="secondary" onPress={() => update('mediaConsent', false)} />
        <Button title={t('settings.deleteHistory')} icon="trash" variant="danger" onPress={clearHistory} />
      </Card>

      <SectionTitle>{t('settings.about')}</SectionTitle>
      <Card>
        <T v="small" color={c.textSecondary}>{t('settings.aboutText')}</T>
        <T v="small" color={c.textSecondary}>{t('common.version')}: 0.1.0</T>
      </Card>
    </Screen>
  );
}

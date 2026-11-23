import Ionicons from '@expo/vector-icons/Ionicons';
import * as Clipboard from 'expo-clipboard';
import { router } from 'expo-router';
import { useState } from 'react';
import { Pressable, TextInput, View } from 'react-native';

import { ApiError, errorKey } from '../../api/client';
import { Card, ErrorBanner, Screen, SectionTitle, T, ToggleRow } from '../../components/ui';
import { checkUrlAndSave } from '../../services/checks';
import { useApp } from '../../state/AppContext';
import { font, radius, space, touch, type IconName } from '../../theme/theme';

export default function CheckScreen() {
  const { c, t, api, repo, settings, update, bumpHistory } = useApp();
  const [url, setUrl] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    if (!url.trim()) {
      setError(t('home.emptyInput'));
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const id = await checkUrlAndSave(api, repo, url, settings.networkChecks);
      bumpHistory();
      setUrl('');
      router.push(`/result/${id}`);
    } catch (e) {
      setError(t(`errors.${errorKey(e instanceof ApiError ? e.code : 'network')}`));
    } finally {
      setBusy(false);
    }
  };

  const paste = async () => {
    const text = await Clipboard.getStringAsync();
    if (text) setUrl(text.trim());
  };

  return (
    <Screen>
      <T v="h2">{t('tabs.check')}</T>

      {/* Ссылка на фишинг — отдельный блок */}
      <SectionTitle>{t('check.linkTitle')}</SectionTitle>
      <T v="small" color={c.textSecondary}>{t('check.linkHint')}</T>
      <Card style={{ gap: space.s, padding: space.m }}>
        <View style={{ flexDirection: 'row', alignItems: 'center', backgroundColor: c.cardAlt, borderRadius: radius.m, borderWidth: 1, borderColor: c.border, paddingLeft: space.m }}>
          <TextInput
            value={url}
            onChangeText={setUrl}
            placeholder={t('home.inputPlaceholder')}
            placeholderTextColor={c.textSecondary}
            autoCapitalize="none"
            autoCorrect={false}
            keyboardType="url"
            returnKeyType="go"
            onSubmitEditing={submit}
            accessibilityLabel={t('home.inputLabel')}
            style={[font.body, { flex: 1, color: c.text, minHeight: touch, paddingHorizontal: space.xs }]}
          />
          <Pressable onPress={paste} accessibilityRole="button" accessibilityLabel={t('home.paste')}
            style={{ minWidth: touch, minHeight: touch, alignItems: 'center', justifyContent: 'center' }}>
            <Ionicons name="clipboard-outline" size={20} color={c.teal} />
          </Pressable>
        </View>
        <Pressable onPress={submit} disabled={busy} accessibilityRole="button" accessibilityLabel={t('check.checkLink')}
          style={({ pressed }) => ({ minHeight: touch, borderRadius: radius.m, backgroundColor: c.teal, alignItems: 'center', justifyContent: 'center', opacity: busy ? 0.6 : pressed ? 0.85 : 1 })}>
          <T v="h3" color={c.onAccent}>{busy ? t('common.loading') : t('check.checkLink')}</T>
        </Pressable>
        <ToggleRow label={t('home.networkToggle')} value={settings.networkChecks} onChange={(v) => update('networkChecks', v)} />
      </Card>
      {error ? <ErrorBanner message={error} /> : null}

      {/* Медиа: фото и видео — отдельно */}
      <SectionTitle>{t('check.mediaTitle')}</SectionTitle>
      <View style={{ flexDirection: 'row', gap: space.m }}>
        <Tile icon="image-outline" title={t('check.photo')} hint={t('check.photoHint')} onPress={() => router.push('/media?kind=image')} />
        <Tile icon="videocam-outline" title={t('check.video')} hint={t('check.videoHint')} onPress={() => router.push('/media?kind=video')} />
      </View>

      {/* Файлы и QR — отдельно */}
      <SectionTitle>{t('check.fileTitle')}</SectionTitle>
      <View style={{ flexDirection: 'row', gap: space.m }}>
        <Tile icon="shield-checkmark-outline" title={t('check.file')} hint={t('check.fileHint')} onPress={() => router.push('/file-scan')} />
        <Tile icon="qr-code-outline" title={t('check.qr')} hint={t('check.qrHint')} onPress={() => router.push('/scan')} />
      </View>
    </Screen>
  );
}

function Tile({ icon, title, hint, onPress }: { icon: IconName; title: string; hint: string; onPress: () => void }) {
  const { c } = useApp();
  return (
    <Pressable onPress={onPress} accessibilityRole="button" accessibilityLabel={`${title}. ${hint}`}
      style={({ pressed }) => ({ flex: 1, opacity: pressed ? 0.8 : 1 })}>
      <Card style={{ minHeight: 132, justifyContent: 'space-between', borderRadius: radius.l }}>
        <View style={{ width: 44, height: 44, borderRadius: radius.m, backgroundColor: c.cardAlt, alignItems: 'center', justifyContent: 'center' }}>
          <Ionicons name={icon} size={22} color={c.teal} />
        </View>
        <View style={{ gap: 2 }}>
          <T v="label">{title}</T>
          <T v="small" color={c.textSecondary}>{hint}</T>
        </View>
      </Card>
    </Pressable>
  );
}

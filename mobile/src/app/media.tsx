import Ionicons from '@expo/vector-icons/Ionicons';
import * as ImagePicker from 'expo-image-picker';
import { router, useLocalSearchParams } from 'expo-router';
import { useEffect, useState } from 'react';
import { ActivityIndicator, Image, Modal, TextInput, View } from 'react-native';

import { ApiError, errorKey } from '../api/client';
import type { Health } from '../api/types';
import { Button, Card, ErrorBanner, Screen, T } from '../components/ui';
import { saveResult } from '../services/checks';
import { useApp } from '../state/AppContext';
import { font, radius, space, touch } from '../theme/theme';

type Phase = 'idle' | 'uploading' | 'processing' | 'downloading';
interface Picked { uri: string; name: string; type: string; kind: 'image' | 'video'; size?: number; duration?: number | null; file?: Blob }

export default function MediaScreen() {
  const { c, t, api, repo, settings, update, bumpHistory } = useApp();
  const [health, setHealth] = useState<Health | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [picked, setPicked] = useState<Picked | null>(null);
  const [link, setLink] = useState('');
  const [phase, setPhase] = useState<Phase>('idle');
  const [error, setError] = useState<string | null>(null);
  const [consentFor, setConsentFor] = useState<null | (() => void)>(null);
  const { kind } = useLocalSearchParams<{ kind?: string }>();
  const only: 'image' | 'video' | null = kind === 'image' || kind === 'video' ? kind : null;

  const loadHealth = () => {
    setHealthError(null);
    api.health().then(setHealth).catch((e) => setHealthError(t(`errors.${errorKey(e instanceof ApiError ? e.code : 'network')}`)));
  };
  useEffect(loadHealth, [api]); // eslint-disable-line react-hooks/exhaustive-deps

  const maxMb = health?.limits.max_upload_mb ?? 50;
  const maxSec = health?.limits.max_video_seconds ?? 60;
  const modelReady = health?.deepfake_model.status === 'configured' || health?.deepfake_model.status === 'loaded';

  const withConsent = (fn: () => void) => {
    if (settings.mediaConsent) fn();
    else setConsentFor(() => fn);
  };

  const pick = async (kind: 'image' | 'video') => {
    setError(null);
    const perm = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!perm.granted) {
      setError(t('errors.permission'));
      return;
    }
    const res = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: kind === 'image' ? ['images'] : ['videos'],
      quality: 0.9, // re-encodes photos (e.g. HEIC) to JPEG, which the server accepts
      preferredAssetRepresentationMode: ImagePicker.UIImagePickerPreferredAssetRepresentationMode.Compatible,
      allowsMultipleSelection: false,
    });
    if (res.canceled || !res.assets?.length) return;
    const a = res.assets[0];
    const durationSec = a.duration ? a.duration / 1000 : null; // picker reports ms
    if (a.fileSize && a.fileSize > maxMb * 1024 * 1024) {
      setError(t('media.tooLargeLocal', { mb: maxMb }));
      return;
    }
    if (kind === 'video' && durationSec && durationSec > maxSec) {
      setError(t('media.tooLongLocal', { sec: maxSec }));
      return;
    }
    setPicked({
      uri: a.uri,
      name: a.fileName || (kind === 'image' ? 'photo.jpg' : 'video.mp4'),
      type: a.mimeType || (kind === 'image' ? 'image/jpeg' : 'video/mp4'),
      kind,
      size: a.fileSize,
      duration: durationSec,
      file: (a as { file?: Blob }).file,
    });
  };

  const finish = async (result: Awaited<ReturnType<typeof api.uploadMedia>>, fileName?: string) => {
    const id = await saveResult(repo, result, fileName);
    bumpHistory();
    router.replace(`/result/${id}`);
  };

  const upload = () =>
    withConsent(async () => {
      if (!picked) return;
      setError(null);
      try {
        const result = await api.uploadMedia({ uri: picked.uri, name: picked.name, type: picked.type, file: picked.file }, setPhase);
        await finish(result, picked.name);
      } catch (e) {
        setError(t(`errors.${errorKey(e instanceof ApiError ? e.code : 'network')}`));
      } finally {
        setPhase('idle');
      }
    });

  const analyzeLink = () =>
    withConsent(async () => {
      if (!link.trim()) return;
      setError(null);
      setPhase('downloading');
      try {
        await finish(await api.checkMediaUrl(link.trim()));
      } catch (e) {
        setError(t(`errors.${errorKey(e instanceof ApiError ? e.code : 'network')}`));
      } finally {
        setPhase('idle');
      }
    });

  const demo = async () => {
    try {
      await finish(await api.demoMedia(), 'demo.mp4');
    } catch (e) {
      setError(t(`errors.${errorKey(e instanceof ApiError ? e.code : 'network')}`));
    }
  };

  const busy = phase !== 'idle';

  return (
    <Screen edges={['bottom']}>
      <T color={c.textSecondary}>{t('media.subtitle', { sec: maxSec, mb: maxMb })}</T>

      {healthError ? <ErrorBanner message={healthError} onRetry={loadHealth} retryLabel={t('common.retry')} /> : null}
      {health && !modelReady ? (
        <Card accent={c.amber} style={{ gap: space.s }}>
          <View style={{ flexDirection: 'row', gap: space.s, alignItems: 'center' }}>
            <Ionicons name="cube-outline" size={22} color={c.amber} />
            <T v="h3" color={c.amber}>{t('media.modelNotConnected')}</T>
          </View>
          <T v="small">{t('media.modelNotConnectedText')}</T>
        </Card>
      ) : null}

      <View style={{ flexDirection: 'row', gap: space.m }}>
        {!only || only === 'image' ? <Button title={t('media.pickImage')} icon="image" variant="secondary" onPress={() => pick('image')} style={{ flex: 1 }} disabled={busy} /> : null}
        {!only || only === 'video' ? <Button title={t('media.pickVideo')} icon="videocam" variant="secondary" onPress={() => pick('video')} style={{ flex: 1 }} disabled={busy} /> : null}
      </View>

      {picked ? (
        <Card style={{ flexDirection: 'row', gap: space.m, alignItems: 'center' }}>
          {picked.kind === 'image' ? (
            <Image source={{ uri: picked.uri }} style={{ width: 72, height: 72, borderRadius: radius.s }} accessibilityIgnoresInvertColors />
          ) : (
            <View style={{ width: 72, height: 72, borderRadius: radius.s, backgroundColor: c.cardAlt, alignItems: 'center', justifyContent: 'center' }}>
              <Ionicons name="film" size={30} color={c.blue} />
            </View>
          )}
          <View style={{ flex: 1 }}>
            <T v="small" color={c.textSecondary}>{t('media.selected')}</T>
            <T v="label" numberOfLines={1}>{picked.name}</T>
            <T v="small" color={c.textSecondary}>
              {picked.size ? `${(picked.size / 1048576).toFixed(1)} MB` : ''}{picked.duration ? ` · ${picked.duration.toFixed(1)} s` : ''}
            </T>
          </View>
        </Card>
      ) : null}
      {picked ? <Button title={t('media.analyze')} icon="scan" onPress={upload} disabled={busy || !modelReady} loading={phase === 'uploading' || phase === 'processing'} /> : null}

      <T v="label" color={c.textSecondary} style={{ marginTop: space.s }}>{t('media.orLink')}</T>
      <TextInput
        value={link}
        onChangeText={setLink}
        placeholder={t('media.linkPlaceholder')}
        placeholderTextColor={c.textSecondary}
        autoCapitalize="none"
        autoCorrect={false}
        keyboardType="url"
        accessibilityLabel={t('media.orLink')}
        style={[font.body, { color: c.text, backgroundColor: c.card, borderRadius: radius.m, borderWidth: 1, borderColor: c.border, minHeight: touch + 4, paddingHorizontal: space.m }]}
      />
      <Button title={t('media.analyzeLink')} icon="link" variant="secondary" onPress={analyzeLink} disabled={busy || !link.trim() || !modelReady} loading={phase === 'downloading'} />

      {busy ? (
        <Card style={{ flexDirection: 'row', gap: space.m, alignItems: 'center' }} accent={c.blue}>
          <ActivityIndicator color={c.blue} />
          <T v="small" style={{ flex: 1 }} >
            {phase === 'uploading' ? t('media.stageUploading') : phase === 'processing' ? t('media.stageProcessing') : t('media.stageDownloading')}
          </T>
        </Card>
      ) : null}
      {error ? <ErrorBanner message={error} /> : null}

      <Button title={t('fileScan.title')} icon="shield-checkmark" variant="secondary" onPress={() => router.push('/file-scan')} disabled={busy} />

      {settings.demoMode ? (
        <Button title={`${t('media.demoMode')} (${t('common.demo')})`} icon="flask" variant="ghost" onPress={demo} disabled={busy} />
      ) : null}

      <Modal visible={!!consentFor} transparent animationType="fade" onRequestClose={() => setConsentFor(null)}>
        <View style={{ flex: 1, backgroundColor: c.overlay, justifyContent: 'center', padding: space.l }}>
          <Card style={{ gap: space.m, padding: space.l }}>
            <Ionicons name="cloud-upload" size={32} color={c.teal} />
            <T v="h2">{t('media.consentTitle')}</T>
            <T v="small" color={c.textSecondary}>{t('media.consentText')}</T>
            <Button title={t('media.consentAccept')} onPress={() => {
              update('mediaConsent', true);
              const fn = consentFor;
              setConsentFor(null);
              fn?.();
            }} />
            <Button title={t('common.cancel')} variant="secondary" onPress={() => setConsentFor(null)} />
          </Card>
        </View>
      </Modal>
    </Screen>
  );
}

import Ionicons from '@expo/vector-icons/Ionicons';
import { CameraView, scanFromURLAsync, useCameraPermissions, type BarcodeScanningResult } from 'expo-camera';
import * as ImagePicker from 'expo-image-picker';
import { router } from 'expo-router';
import { useRef, useState } from 'react';
import { View } from 'react-native';

import { ApiError, errorKey } from '../api/client';
import { Button, Card, EmptyState, ErrorBanner, Screen, T } from '../components/ui';
import { checkUrlAndSave, previewDomain } from '../services/checks';
import { useApp } from '../state/AppContext';
import { radius, space } from '../theme/theme';

export default function ScanScreen() {
  const { c, t, api, repo, settings, bumpHistory } = useApp();
  const [permission, requestPermission] = useCameraPermissions();
  const [data, setData] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const locked = useRef(false);

  const onScanned = (r: BarcodeScanningResult) => {
    if (locked.current) return;
    locked.current = true; // show the content; never open it automatically
    setData(r.data);
  };

  const fromImage = async () => {
    setError(null);
    const res = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ['images'], quality: 1 });
    if (res.canceled || !res.assets?.length) return;
    try {
      const found = await scanFromURLAsync(res.assets[0].uri, ['qr']);
      if (!found.length) setError(t('qr.noCode'));
      else {
        locked.current = true;
        setData(found[0].data);
      }
    } catch {
      setError(t('qr.noCode'));
    }
  };

  const analyze = async () => {
    if (!data) return;
    setBusy(true);
    setError(null);
    try {
      const id = await checkUrlAndSave(api, repo, data, settings.networkChecks);
      bumpHistory();
      router.replace(`/result/${id}`);
    } catch (e) {
      setError(t(`errors.${errorKey(e instanceof ApiError ? e.code : 'network')}`));
    } finally {
      setBusy(false);
    }
  };

  const reset = () => {
    setData(null);
    setError(null);
    locked.current = false;
  };

  if (!permission) return <Screen edges={['bottom']}><T>{t('common.loading')}</T></Screen>;

  const preview = data ? previewDomain(data) : null;

  return (
    <Screen edges={['bottom']}>
      <T color={c.textSecondary}>{t('qr.hint')}</T>
      {!permission.granted ? (
        <Card>
          <EmptyState icon="camera-outline" title={t('qr.permissionTitle')} hint={t('qr.permissionText')}
            action={<Button title={t('qr.grant')} onPress={requestPermission} />} />
        </Card>
      ) : !data ? (
        <View style={{ height: 340, borderRadius: radius.l, overflow: 'hidden', borderWidth: 2, borderColor: c.teal }}>
          <CameraView style={{ flex: 1 }} facing="back" barcodeScannerSettings={{ barcodeTypes: ['qr'] }} onBarcodeScanned={onScanned} />
        </View>
      ) : null}

      <Button title={t('qr.fromImage')} icon="images-outline" variant="secondary" onPress={fromImage} />

      {data && preview ? (
        <Card accent={preview.isUrl ? c.blue : c.border} style={{ gap: space.s }}>
          <View style={{ flexDirection: 'row', gap: space.s, alignItems: 'center' }}>
            <Ionicons name={preview.isUrl ? 'link' : 'document-text-outline'} size={20} color={c.blue} />
            <T v="h3">{preview.isUrl ? t('qr.found') : t('qr.notUrl')}</T>
          </View>
          {preview.domain ? <T v="h2" selectable>{t('qr.domain', { domain: preview.domain })}</T> : null}
          <T v="small" color={c.textSecondary} selectable numberOfLines={4}>{data}</T>
          {preview.isUrl ? <Button title={t('qr.analyze')} icon="shield-checkmark" onPress={analyze} loading={busy} /> : null}
          <Button title={t('qr.scanAgain')} variant="ghost" onPress={reset} />
        </Card>
      ) : null}
      {error ? <ErrorBanner message={error} /> : null}
    </Screen>
  );
}

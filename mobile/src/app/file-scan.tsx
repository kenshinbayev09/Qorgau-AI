import Ionicons from '@expo/vector-icons/Ionicons';
import * as DocumentPicker from 'expo-document-picker';
import { Linking, View } from 'react-native';
import { useState } from 'react';

import { ApiError, errorKey } from '../api/client';
import type { FileScanResult } from '../api/types';
import { Button, Card, ErrorBanner, Screen, T, ToggleRow } from '../components/ui';
import { useApp } from '../state/AppContext';
import { riskMeta, space } from '../theme/theme';

interface Picked { uri: string; name: string; type: string; size?: number; file?: Blob }

export default function FileScanScreen() {
  const { c, t, api, settings, update } = useApp();
  const [picked, setPicked] = useState<Picked | null>(null);
  const [sendFile, setSendFile] = useState(false);
  const [consentOpen, setConsentOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<FileScanResult | null>(null);

  const pick = async () => {
    setError(null);
    setResult(null);
    const res = await DocumentPicker.getDocumentAsync({ copyToCacheDirectory: true, multiple: false });
    if (res.canceled || !res.assets?.length) return;
    const a = res.assets[0];
    setPicked({ uri: a.uri, name: a.name, type: a.mimeType || 'application/octet-stream', size: a.size, file: (a as { file?: Blob }).file });
  };

  const run = async (allowUpload: boolean) => {
    if (!picked) return;
    setBusy(true);
    setError(null);
    try {
      setResult(await api.scanFile({ uri: picked.uri, name: picked.name, type: picked.type, file: picked.file }, allowUpload));
    } catch (e) {
      setError(t(`errors.${errorKey(e instanceof ApiError ? e.code : 'network')}`));
    } finally {
      setBusy(false);
    }
  };

  const scan = () => {
    if (!sendFile) return run(false);
    if (settings.fileUploadConsent) return run(true);
    setConsentOpen(true);
  };

  const verdictColor = result?.verdict === 'malicious' ? c.red : result?.verdict === 'suspicious' ? c.amber : result?.verdict === 'clean' ? c.green : c.neutral;
  const verdictKey = result?.verdict ? `fileScan.verdict${result.verdict[0].toUpperCase()}${result.verdict.slice(1)}` : null;
  const meta = riskMeta(c, result?.verdict === 'clean' ? 'low' : result?.verdict === 'suspicious' ? 'suspicious' : result?.verdict === 'malicious' ? 'high' : 'insufficient');

  return (
    <Screen edges={['bottom']}>
      <T color={c.textSecondary}>{t('fileScan.subtitle')}</T>

      <Button title={t('fileScan.pick')} icon="document-attach" variant="secondary" onPress={pick} disabled={busy} />

      {picked ? (
        <Card style={{ gap: 4 }}>
          <T v="small" color={c.textSecondary}>{t('fileScan.selected')}</T>
          <T v="label" numberOfLines={1}>{picked.name}</T>
          {picked.size ? <T v="small" color={c.textSecondary}>{(picked.size / 1048576).toFixed(2)} MB</T> : null}
        </Card>
      ) : null}

      <ToggleRow label={t('fileScan.sendToggle')} hint={t('fileScan.sendHint')} value={sendFile} onChange={setSendFile} />

      <Button title={t('fileScan.scan')} icon="shield-checkmark" onPress={scan} disabled={!picked || busy} loading={busy} />

      {error ? <ErrorBanner message={error} /> : null}

      {result ? (
        <Card accent={verdictColor} style={{ gap: space.s }}>
          {result.status === 'done' && verdictKey ? (
            <>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.s }}>
                <Ionicons name={meta.icon} size={24} color={verdictColor} />
                <T v="h3" color={verdictColor} style={{ flex: 1 }}>{t(verdictKey)}</T>
              </View>
              {result.stats ? (
                <T v="small" color={c.textSecondary}>
                  {t('fileScan.counts', {
                    malicious: result.stats.malicious ?? 0,
                    suspicious: result.stats.suspicious ?? 0,
                    harmless: result.stats.harmless ?? 0,
                    undetected: result.stats.undetected ?? 0,
                  })}
                </T>
              ) : null}
              <T v="small" color={c.textSecondary}>
                {result.source === 'uploaded' ? t('fileScan.sourceUploaded') : t('fileScan.source')}
              </T>
              <Button title={t('fileScan.openReport')} variant="ghost" icon="open-outline" onPress={() => Linking.openURL(result.permalink)} />
            </>
          ) : (
            <T v="small">{t(
              result.status === 'upload_required' ? 'fileScan.uploadRequired'
                : result.status === 'too_large' ? 'fileScan.tooLarge'
                : result.status === 'disabled' ? 'fileScan.disabled'
                : result.status === 'rate_limited' ? 'fileScan.rateLimited'
                : result.status === 'timeout' ? 'fileScan.timeout'
                : 'fileScan.failed',
            )}</T>
          )}
          <T v="small" color={c.textSecondary}>{t('common.modelEstimate')}</T>
        </Card>
      ) : null}

      {consentOpen ? (
        <Card accent={c.amber} style={{ gap: space.s }}>
          <T v="h3">{t('fileScan.consentTitle')}</T>
          <T v="small" color={c.textSecondary}>{t('fileScan.consentText')}</T>
          <Button title={t('fileScan.consentAccept')} onPress={() => {
            update('fileUploadConsent', true);
            setConsentOpen(false);
            run(true);
          }} />
          <Button title={t('common.cancel')} variant="secondary" onPress={() => setConsentOpen(false)} />
        </Card>
      ) : null}
    </Screen>
  );
}

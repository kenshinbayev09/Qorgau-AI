import Ionicons from '@expo/vector-icons/Ionicons';
import * as Clipboard from 'expo-clipboard';
import { router, useLocalSearchParams } from 'expo-router';
import { useEffect, useState } from 'react';
import { ActivityIndicator, Image, View } from 'react-native';

import type { MediaResult, UrlResult } from '../../api/types';
import { CheckList, FrameStrip, RiskBadge, ScoreGauge, SignalCard, StageList } from '../../components/risk';
import { Button, Card, Collapsible, EmptyState, FadeIn, Screen, SectionTitle, T } from '../../components/ui';
import type { HistoryEntry } from '../../db/history';
import { useApp } from '../../state/AppContext';
import { riskMeta, space } from '../../theme/theme';

export default function ResultScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { repo, t, c } = useApp();
  const [entry, setEntry] = useState<HistoryEntry | null | undefined>(undefined);

  useEffect(() => {
    repo.get(String(id)).then(setEntry).catch(() => setEntry(null));
  }, [id, repo]);

  if (entry === undefined) {
    return <Screen edges={[]}><ActivityIndicator color={c.teal} style={{ marginTop: space.xl }} /></Screen>;
  }
  if (entry === null) {
    return <Screen edges={[]}><EmptyState icon="document-outline" title={t('result.notFound')} /></Screen>;
  }
  const r = entry.result;
  const m = riskMeta(c, r.category);

  return (
    <Screen edges={['bottom']}>
      {r.kind === 'media' && r.demo ? (
        <Card accent={c.amber} style={{ flexDirection: 'row', gap: space.s, alignItems: 'center', backgroundColor: c.amber + '1A' }}>
          <Ionicons name="flask" size={22} color={c.amber} />
          <View style={{ flex: 1 }}>
            <T v="h3" color={c.amber}>{t('common.demo')}</T>
            <T v="small">{t('result.demoBanner')}</T>
          </View>
        </Card>
      ) : null}

      <FadeIn>
        <Card style={{ alignItems: 'center', gap: space.m, paddingVertical: space.l, borderColor: m.color + '66' }}>
          <ScoreGauge score={r.score} category={r.category} />
          <RiskBadge category={r.category} />
          <T style={{ textAlign: 'center' }}>{t(`riskSummary.${r.kind}.${r.category}`)}</T>
          <T v="small" color={c.textSecondary} style={{ textAlign: 'center' }}>{t('common.modelEstimate')}</T>
        </Card>
      </FadeIn>

      {r.kind === 'url' ? <UrlDetails r={r} /> : <MediaDetails r={r} title={entry.title} />}

      <View style={{ gap: space.s, marginTop: space.s }}>
        <Button title={t('result.explainAi')} icon="sparkles" onPress={() => router.push({ pathname: '/assistant', params: { attach: entry.id } })} />
        <Button title={t('result.checkAnother')} icon="refresh" variant="secondary" onPress={() => router.dismissTo('/')} />
      </View>
    </Screen>
  );
}

function UrlDetails({ r }: { r: UrlResult }) {
  const { c, t } = useApp();
  const [copied, setCopied] = useState(false);
  const positive = r.signals.filter((s) => s.weight > 0);
  const info = r.signals.filter((s) => s.weight <= 0);
  const hops = r.redirects?.hops ?? [];
  return (
    <>
      <Card>
        <T v="label" color={c.textSecondary}>{t('result.domain')}</T>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.s }}>
          <T v="h2" style={{ flex: 1 }} selectable>{r.normalized.registered_domain}</T>
          <Button title={copied ? t('result.copied') : t('result.copyDomain')} variant="ghost" style={{ minHeight: 40 }}
            onPress={() => Clipboard.setStringAsync(r.normalized.registered_domain).then(() => setCopied(true))} />
        </View>
        <T v="small" color={c.textSecondary} selectable numberOfLines={3}>{r.input}</T>
        <View style={{ flexDirection: 'row', gap: space.s, alignItems: 'center' }}>
          <Ionicons name="eye-off-outline" size={16} color={c.textSecondary} />
          <T v="small" color={c.textSecondary}>{t('result.notOpened')}</T>
        </View>
      </Card>

      <SectionTitle>{t('result.signals')}</SectionTitle>
      {positive.length === 0 ? <Card><T v="small" color={c.textSecondary}>{t('result.noSignals')}</T></Card> : null}
      {positive.map((s, i) => <FadeIn key={s.id} delay={40 * i}><SignalCard s={s} /></FadeIn>)}
      {info.map((s) => <SignalCard key={s.id} s={s} />)}

      <SectionTitle>{t('result.advice')}</SectionTitle>
      <Card>
        {r.advice.map((a) => (
          <View key={a} style={{ flexDirection: 'row', gap: space.s }}>
            <Ionicons name="checkmark" size={18} color={c.teal} />
            <T v="small" style={{ flex: 1 }}>{t(`advice.${a}`)}</T>
          </View>
        ))}
      </Card>

      <Collapsible title={t('result.howChecked')}>
        <CheckList checks={r.checks} />
        <T v="small" color={c.textSecondary}>
          {t('result.components', {
            model: r.score_components.model === null ? '—' : Math.round(r.score_components.model * 100),
            rules: Math.round(r.score_components.rules * 100),
          })}
        </T>
        {r.model.version ? <T v="small" color={c.textSecondary}>{t('result.modelVersion', { version: r.model.version })}</T> : null}
        <T v="label" style={{ marginTop: space.s }}>{t('result.redirects')}</T>
        {hops.length <= 1 && !r.redirects?.error_code ? <T v="small" color={c.textSecondary}>{t('result.noRedirects')}</T> : null}
        {hops.map((h, i) => (
          <View key={i} style={{ flexDirection: 'row', gap: space.s }}>
            <T v="small" color={h.blocked_reason ? c.red : c.textSecondary}>{i + 1}.</T>
            <T v="small" style={{ flex: 1 }} numberOfLines={2}>
              {h.host} {h.status ? `· ${h.status}` : ''} {h.blocked_reason ? `· ${h.blocked_reason}` : ''}
            </T>
          </View>
        ))}
        <T v="small" color={c.textSecondary}>{t('result.analyzedAt')}: {new Date(r.analyzed_at).toLocaleString()}</T>
      </Collapsible>
    </>
  );
}

function MediaDetails({ r, title }: { r: MediaResult; title: string }) {
  const { c, t } = useApp();
  const preview = r.frames.find((f) => f.index === r.top_frames[0]) ?? r.frames[0];
  return (
    <>
      <Card style={{ flexDirection: 'row', gap: space.m, alignItems: 'center' }}>
        <View style={{ width: 64, height: 64, borderRadius: 16, overflow: 'hidden', backgroundColor: c.cardAlt, alignItems: 'center', justifyContent: 'center' }}>
          {preview?.thumb ? (
            <Image source={{ uri: preview.thumb }} style={{ width: 64, height: 64 }} accessibilityIgnoresInvertColors />
          ) : (
            <Ionicons name={r.media_type === 'video' ? 'film' : 'image'} size={28} color={c.textSecondary} />
          )}
        </View>
        <View style={{ flex: 1 }}>
          <T v="label" numberOfLines={1}>{title}</T>
          <T v="small" color={c.textSecondary}>
            {r.media_type} · {r.format}{r.meta?.duration_s ? ` · ${r.meta.duration_s} s` : ''}
          </T>
          <T v="small" color={c.textSecondary}>{t('result.model')}: {r.model.name}{r.model.version ? ` @ ${r.model.version}` : ''}</T>
        </View>
      </Card>

      {r.reason ? (
        <Card accent={c.neutral} style={{ flexDirection: 'row', gap: space.s }}>
          <Ionicons name="scan-outline" size={20} color={c.neutral} />
          <T v="small" style={{ flex: 1 }}>{t(`mediaReason.${r.reason}`)}</T>
        </Card>
      ) : null}

      <SectionTitle>{t('result.frames')}</SectionTitle>
      <Card>
        <FrameStrip frames={r.frames} highlight={r.top_frames} />
        <T v="small" color={c.textSecondary}>
          {t('result.aggregate', { n: r.aggregate.frames_with_face, total: r.aggregate.frames_sampled })}
          {r.aggregate.max !== null ? ` · max ${Math.round(r.aggregate.max * 100)}` : ''}
        </T>
        <T v="small" color={c.amber}>{t('result.frameNote')}</T>
      </Card>

      <Collapsible title={t('result.howChecked')}>
        <T v="label">{t('result.stages')}</T>
        <StageList stages={r.stages} />
        <T v="label" style={{ marginTop: space.s }}>{t('result.limitations')}</T>
        {r.limitations.map((l) => (
          <View key={l} style={{ flexDirection: 'row', gap: space.s }}>
            <Ionicons name="alert-circle-outline" size={16} color={c.textSecondary} />
            <T v="small" style={{ flex: 1 }}>{t(`limitation.${l}`)}</T>
          </View>
        ))}
      </Collapsible>
    </>
  );
}


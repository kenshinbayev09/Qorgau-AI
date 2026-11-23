import Ionicons from '@expo/vector-icons/Ionicons';
import { useEffect, useRef } from 'react';
import { Animated, Image, Pressable, ScrollView, View } from 'react-native';
import Svg, { Circle } from 'react-native-svg';

import type { CheckItem, Frame, Signal } from '../api/types';
import type { HistoryEntry } from '../db/history';
import { useApp } from '../state/AppContext';
import { radius, riskMeta, severityColor, space, touch, type Category } from '../theme/theme';
import { Card, T } from './ui';

const AnimatedCircle = Animated.createAnimatedComponent(Circle);

export function RiskBadge({ category, compact }: { category: Category | string; compact?: boolean }) {
  const { c, t } = useApp();
  const m = riskMeta(c, category);
  return (
    <View
      accessible
      accessibilityLabel={t(`risk.${category}`)}
      style={{
        flexDirection: 'row', alignItems: 'center', gap: 6, alignSelf: 'flex-start',
        paddingHorizontal: compact ? 8 : 12, paddingVertical: compact ? 4 : 6,
        borderRadius: radius.pill, backgroundColor: m.color + '22', borderWidth: 1, borderColor: m.color + '66',
      }}
    >
      <Ionicons name={m.icon} size={compact ? 14 : 18} color={m.color} />
      <T v="label" color={m.color}>{t(`risk.${category}`)}</T>
    </View>
  );
}

/** Circular score indicator. Shows the numeric model score; "—" when no score exists. */
export function ScoreGauge({ score, category, size = 132 }: { score: number | null; category: Category | string; size?: number }) {
  const { c, t } = useApp();
  const m = riskMeta(c, category);
  const stroke = 12;
  const r = (size - stroke) / 2;
  const circ = 2 * Math.PI * r;
  const anim = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    Animated.timing(anim, { toValue: score ?? 0, duration: 700, useNativeDriver: false }).start();
  }, [anim, score]);
  const offset = anim.interpolate({ inputRange: [0, 1], outputRange: [circ, 0] });
  const pct = score === null ? '—' : `${Math.round(score * 100)}`;
  return (
    <View style={{ width: size, height: size, alignItems: 'center', justifyContent: 'center' }} accessible
      accessibilityLabel={`${t('common.score')}: ${score === null ? t('risk.insufficient') : pct + '/100'}`}>
      <Svg width={size} height={size} style={{ position: 'absolute', transform: [{ rotate: '-90deg' }] }}>
        <Circle cx={size / 2} cy={size / 2} r={r} stroke={c.border} strokeWidth={stroke} fill="none" />
        {score !== null ? (
          <AnimatedCircle cx={size / 2} cy={size / 2} r={r} stroke={m.color} strokeWidth={stroke} fill="none"
            strokeDasharray={`${circ} ${circ}`} strokeDashoffset={offset} strokeLinecap="round" />
        ) : null}
      </Svg>
      <Ionicons name={m.icon} size={22} color={m.color} />
      <T v="h1" color={c.text}>{pct}</T>
      <T v="small" color={c.textSecondary}>/ 100</T>
    </View>
  );
}

export function SignalCard({ s }: { s: Signal }) {
  const { c, t } = useApp();
  const color = severityColor(c, s.severity);
  const params = Object.fromEntries(Object.entries(s.params).map(([k, v]) => [k, Array.isArray(v) ? v.join(', ') : v === null ? '—' : String(v)]));
  const icon = s.weight < 0 ? 'checkmark-circle' : s.severity === 'high' ? 'alert-circle' : s.severity === 'medium' ? 'alert' : 'information-circle';
  return (
    <View
      accessible
      accessibilityLabel={`${t(`signal.${s.id}.t`, params)}. ${t(`signal.${s.id}.d`, params)}`}
      style={{ flexDirection: 'row', gap: space.s, padding: space.m, borderRadius: radius.m, backgroundColor: c.cardAlt, borderLeftWidth: 4, borderLeftColor: color }}
    >
      <Ionicons name={icon} size={20} color={color} style={{ marginTop: 1 }} />
      <View style={{ flex: 1, gap: 2 }}>
        <View style={{ flexDirection: 'row', justifyContent: 'space-between', gap: space.s }}>
          <T v="label" style={{ flex: 1 }}>{t(`signal.${s.id}.t`, params)}</T>
          {s.weight > 0 ? <T v="small" color={color}>{t(`severity.${s.severity}`)}</T> : null}
        </View>
        <T v="small" color={c.textSecondary}>{t(`signal.${s.id}.d`, params)}</T>
      </View>
    </View>
  );
}

export function CheckList({ checks }: { checks: CheckItem[] }) {
  const { c, t } = useApp();
  return (
    <View style={{ gap: space.s }}>
      {checks.map((ch) => {
        const ok = ch.status === 'done';
        const color = ok ? c.green : ch.status === 'stopped' ? c.amber : c.neutral;
        return (
          <View key={ch.id} style={{ flexDirection: 'row', gap: space.s, alignItems: 'flex-start' }} accessible>
            <Ionicons name={ok ? 'checkmark-circle' : ch.status === 'stopped' ? 'hand-left' : 'remove-circle'} size={18} color={color} />
            <View style={{ flex: 1 }}>
              <T v="small">{t(`checks.${ch.id}`)}</T>
              <T v="small" color={color}>
                {t(`checkStatus.${ch.status}`)}{ch.detail && ch.status !== 'done' ? ` · ${ch.detail}` : ''}
              </T>
            </View>
          </View>
        );
      })}
    </View>
  );
}

export function StageList({ stages }: { stages: { id: string; status: string; ms: number }[] }) {
  const { c, t } = useApp();
  return (
    <View style={{ gap: 6 }}>
      {stages.map((s) => (
        <View key={s.id} style={{ flexDirection: 'row', alignItems: 'center', gap: space.s }}>
          <Ionicons name="checkmark-done" size={16} color={c.teal} />
          <T v="small" style={{ flex: 1 }}>{t(`stage.${s.id}`)}</T>
          <T v="small" color={c.textSecondary}>{s.ms} ms</T>
        </View>
      ))}
    </View>
  );
}

export function FrameStrip({ frames, highlight }: { frames: Frame[]; highlight: number[] }) {
  const { c, t } = useApp();
  return (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: space.s }}>
      {frames.map((f) => {
        const color = f.score === null ? c.neutral : f.score >= 0.7 ? c.red : f.score >= 0.4 ? c.amber : c.green;
        const top = highlight.includes(f.index);
        return (
          <View key={f.index} style={{ width: 88, gap: 4 }} accessible
            accessibilityLabel={`${f.t_sec} s: ${f.score === null ? t('result.noFace') : Math.round(f.score * 100) + '/100'}`}>
            <View style={{ width: 88, height: 88, borderRadius: radius.s, overflow: 'hidden', borderWidth: top ? 3 : 1, borderColor: top ? color : c.border, backgroundColor: c.cardAlt, alignItems: 'center', justifyContent: 'center' }}>
              {f.thumb ? <Image source={{ uri: f.thumb }} style={{ width: '100%', height: '100%' }} /> : <Ionicons name="image-outline" size={26} color={c.textSecondary} />}
            </View>
            <T v="small" color={color} style={{ textAlign: 'center' }}>
              {f.score === null ? t('result.noFace') : `${Math.round(f.score * 100)}`}
            </T>
            <T v="small" color={c.textSecondary} style={{ textAlign: 'center' }}>{f.t_sec.toFixed(1)} s</T>
          </View>
        );
      })}
    </ScrollView>
  );
}

export function HistoryRow({ e, onPress, onDelete }: { e: HistoryEntry; onPress: () => void; onDelete?: () => void }) {
  const { c, t, lang } = useApp();
  const m = riskMeta(c, e.category);
  const date = new Date(e.createdAt).toLocaleString(lang === 'kk' ? 'kk-KZ' : lang === 'en' ? 'en-GB' : 'ru-RU', { dateStyle: 'short', timeStyle: 'short' });
  return (
    <Pressable onPress={onPress} accessibilityRole="button"
      accessibilityLabel={`${e.title}. ${t(`risk.${e.category}`)}. ${date}`}
      style={({ pressed }) => ({ opacity: pressed ? 0.8 : 1 })}>
      <Card style={{ flexDirection: 'row', alignItems: 'center', gap: space.m, paddingVertical: space.s, minHeight: touch + 16 }}>
        <View style={{ width: 40, height: 40, borderRadius: 20, backgroundColor: m.color + '22', alignItems: 'center', justifyContent: 'center' }}>
          <Ionicons name={e.kind === 'url' ? 'link' : 'film'} size={20} color={m.color} />
        </View>
        <View style={{ flex: 1, gap: 2 }}>
          <T v="label" numberOfLines={1}>{e.title}</T>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.s, flexWrap: 'wrap' }}>
            <T v="small" color={m.color}>{t(`risk.${e.category}`)}</T>
            {e.demo ? <T v="small" color={c.amber}>· {t('common.demo')}</T> : null}
            <T v="small" color={c.textSecondary}>· {date}</T>
          </View>
        </View>
        {onDelete ? (
          <Pressable onPress={onDelete} hitSlop={10} accessibilityRole="button" accessibilityLabel={t('common.delete')}
            style={{ width: touch, height: touch, alignItems: 'center', justifyContent: 'center' }}>
            <Ionicons name="trash-outline" size={20} color={c.textSecondary} />
          </Pressable>
        ) : (
          <Ionicons name="chevron-forward" size={20} color={c.textSecondary} />
        )}
      </Card>
    </Pressable>
  );
}

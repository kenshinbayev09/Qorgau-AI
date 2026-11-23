import Ionicons from '@expo/vector-icons/Ionicons';
import { router, useLocalSearchParams } from 'expo-router';
import { useEffect, useState } from 'react';
import { TextInput, View } from 'react-native';

import { ApiError, errorKey } from '../../api/client';
import type { AgentResponse, CheckResult } from '../../api/types';
import { Button, Card, Collapsible, ErrorBanner, FadeIn, Screen, T, ToggleRow } from '../../components/ui';
import type { HistoryEntry } from '../../db/history';
import type { Params } from '../../i18n/translate';
import { saveResult } from '../../services/checks';
import { renderBlocks } from '../../services/explain';
import { useApp } from '../../state/AppContext';
import { font, radius, riskMeta, space, touch } from '../../theme/theme';

export default function Assistant() {
  const { c, t, lang, api, repo, settings, update, bumpHistory } = useApp();
  const params = useLocalSearchParams<{ attach?: string }>();
  const [text, setText] = useState('');
  const [attached, setAttached] = useState<HistoryEntry | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [resp, setResp] = useState<AgentResponse | null>(null);
  const [savedId, setSavedId] = useState<string | null>(null);

  useEffect(() => {
    if (params.attach) repo.get(String(params.attach)).then((e) => e && setAttached(e)).catch(() => undefined);
  }, [params.attach, repo]);

  const attachLatest = async () => {
    const [latest] = await repo.list({ limit: 1 });
    if (latest) setAttached(latest);
  };

  const run = async () => {
    if (!text.trim() && !attached) return;
    setBusy(true);
    setError(null);
    setResp(null);
    setSavedId(attached?.id ?? null);
    try {
      const r = await api.runAgent({
        text,
        attached_result: attached?.result,
        lang,
        allow_network: settings.networkChecks,
        use_llm: settings.useLlm,
      });
      setResp(r);
    } catch (e) {
      setError(t(`errors.${errorKey(e instanceof ApiError ? e.code : 'network')}`));
    } finally {
      setBusy(false);
    }
  };

  const ensureSaved = async (result: CheckResult): Promise<string> => {
    if (savedId) return savedId;
    const id = await saveResult(repo, result);
    bumpHistory();
    setSavedId(id);
    return id;
  };

  const onAction = async (a: string) => {
    if (a === 'paste_link' || a === 'check_another' || a === 'try_again') {
      setResp(null);
      setAttached(null);
      setText('');
    } else if (a === 'check_media' || a === 'upload_media') router.push('/media');
    else if (a === 'scan_qr') router.push('/scan');
    else if ((a === 'open_result' || a === 'save_result') && resp?.result) {
      const id = await ensureSaved(resp.result);
      if (a === 'open_result') router.push(`/result/${id}`);
    }
  };

  const signalParams: Record<string, Params> = {};
  if (resp?.result?.kind === 'url') {
    for (const s of resp.result.signals) {
      signalParams[s.id] = Object.fromEntries(Object.entries(s.params).map(([k, v]) => [k, Array.isArray(v) ? v.join(', ') : v === null ? null : String(v)]));
    }
  }
  const sentences = resp ? renderBlocks(resp.explanation.blocks, t, signalParams) : [];
  const verdict = resp?.result ? riskMeta(c, resp.result.category) : null;

  return (
    <Screen>
      <T v="h1">{t('assistant.title')}</T>
      <T color={c.textSecondary}>{t('assistant.subtitle')}</T>

      <Card style={{ gap: space.m }}>
        <TextInput
          value={text}
          onChangeText={setText}
          placeholder={t('assistant.placeholder')}
          placeholderTextColor={c.textSecondary}
          multiline
          autoCapitalize="none"
          accessibilityLabel={t('assistant.placeholder')}
          style={[font.body, { color: c.text, minHeight: 96, textAlignVertical: 'top', backgroundColor: c.cardAlt, borderRadius: radius.m, padding: space.m }]}
        />
        {attached ? (
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.s }}>
            <Ionicons name="attach" size={18} color={c.teal} />
            <T v="small" style={{ flex: 1 }} numberOfLines={1}>{t('assistant.attached', { name: attached.title })}</T>
            <Button title={t('common.delete')} variant="ghost" onPress={() => setAttached(null)} style={{ minHeight: 40 }} />
          </View>
        ) : (
          <Button title={t('assistant.attach')} icon="attach" variant="ghost" onPress={attachLatest} />
        )}
        <ToggleRow label={t('assistant.useLlm')} value={settings.useLlm} onChange={(v) => update('useLlm', v)} />
        <Button title={t('assistant.send')} icon="send" onPress={run} loading={busy} disabled={!text.trim() && !attached} />
        <View style={{ flexDirection: 'row', gap: space.s }}>
          <Ionicons name="lock-closed-outline" size={14} color={c.textSecondary} />
          <T v="small" color={c.textSecondary} style={{ flex: 1 }}>{t('assistant.untrusted')}</T>
        </View>
      </Card>

      {!resp && !busy && !error ? <T v="small" color={c.textSecondary}>{t('assistant.empty')}</T> : null}
      {error ? <ErrorBanner message={error} onRetry={run} retryLabel={t('common.retry')} /> : null}

      {resp ? (
        <FadeIn style={{ gap: space.m }}>
          <Card accent={verdict?.color}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.s }}>
              <Ionicons name={resp.state === 'done' ? 'sparkles' : resp.state === 'failed' ? 'close-circle' : 'help-circle'} size={20}
                color={resp.state === 'failed' ? c.red : c.teal} />
              <T v="label">{t(`agentState.${resp.state}`)}</T>
              <T v="small" color={c.textSecondary}>· {t(`agentInput.${resp.input_type}`)}{resp.tool_used ? ` → ${t(`agentTool.${resp.tool_used}`)}` : ''}</T>
            </View>
            {resp.explanation.text ? (
              <>
                <T v="small" color={c.textSecondary}>{t('assistant.llmText')}</T>
                <T selectable>{resp.explanation.text}</T>
                <T v="small" color={c.textSecondary} style={{ marginTop: space.s }}>{t('assistant.templateText')}</T>
              </>
            ) : null}
            {sentences.map((s, i) => <T key={i} v={i === 0 ? 'body' : 'small'} color={i === 0 ? c.text : c.textSecondary}>{s}</T>)}
          </Card>

          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: space.s }}>
            {resp.actions.map((a) => (
              <Button key={a} title={t(`agentAction.${a}`)} variant={a === 'open_result' ? 'primary' : 'secondary'} onPress={() => onAction(a)}
                style={{ minHeight: touch, flexGrow: 1 }} />
            ))}
          </View>

          <Collapsible title={t('assistant.trace')} icon="git-branch-outline">
            {resp.trace.map((s) => (
              <View key={s.step} style={{ flexDirection: 'row', gap: space.s }}>
                <T v="small" color={c.teal} style={{ width: 22 }}>{s.step}.</T>
                <View style={{ flex: 1 }}>
                  <T v="small">{t(`agentState.${s.state}`)} · <T v="small" color={c.textSecondary}>{s.action}</T></T>
                  {Object.keys(s.detail).length ? (
                    <T v="small" color={c.textSecondary} selectable>
                      {Object.entries(s.detail).map(([k, v]) => `${k}=${typeof v === 'object' ? JSON.stringify(v) : String(v)}`).join(', ')}
                    </T>
                  ) : null}
                </View>
                <T v="small" color={c.textSecondary}>{s.ms} ms</T>
              </View>
            ))}
            <T v="label" style={{ marginTop: space.s }}>{t('assistant.tools')}</T>
            {resp.tools.map((tool) => (
              <View key={tool.name} style={{ flexDirection: 'row', gap: space.s, alignItems: 'center' }}>
                <Ionicons name={tool.available ? 'checkmark-circle' : 'remove-circle'} size={16} color={tool.available ? c.green : c.neutral} />
                <T v="small">{t(`agentTool.${tool.name}`)}{tool.reason ? ` · ${tool.reason}` : ''}</T>
              </View>
            ))}
          </Collapsible>
        </FadeIn>
      ) : null}
    </Screen>
  );
}

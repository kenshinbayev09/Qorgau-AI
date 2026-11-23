// Renders the agent's structured explanation blocks into localised sentences.
// The blocks only contain ids/enums/numbers produced by the backend from real results.
import type { ExplanationBlock } from '../api/types';
import type { Params } from '../i18n/translate';

type TFn = (key: string, params?: Params) => string;

export function renderBlocks(blocks: ExplanationBlock[], t: TFn, signalParams: Record<string, Params> = {}): string[] {
  const out: string[] = [];
  for (const b of blocks) {
    switch (b.type) {
      case 'verdict': {
        const score = b.score === null ? '' : t('agentBlock.scorePart', { score: Math.round(b.score * 100) + '/100' });
        const category = t(`risk.${b.category}`);
        if (b.kind === 'media') out.push(t('agentBlock.verdictMedia', { category, score }));
        else out.push(t('agentBlock.verdictUrl', { category, score, domain: b.domain ? t('agentBlock.domainPart', { domain: b.domain }) : '' }));
        break;
      }
      case 'reason': {
        const p = signalParams[b.signal] ?? {};
        out.push(t('agentBlock.reason', { title: t(`signal.${b.signal}.t`, p), desc: t(`signal.${b.signal}.d`, p) }));
        break;
      }
      case 'media_summary':
        out.push(t('agentBlock.mediaSummary', {
          sampled: b.frames_sampled ?? '—',
          faces: b.frames_with_face ?? '—',
          max: b.max_frame_score == null ? '—' : Math.round(b.max_frame_score * 100) + '/100',
        }));
        if (b.reason) out.push(t(`mediaReason.${b.reason}`));
        break;
      case 'checks_not_done':
        out.push(t('agentBlock.checksNotDone', { checks: b.checks.map((c) => t(`checks.${c}`)).join('; ') }));
        break;
      case 'advice':
        out.push(t('agentBlock.advice', { text: t(`advice.${b.id}`) }));
        break;
      case 'note':
        out.push(t(`agentNote.${b.id.split(':')[0]}`));
        break;
      case 'need_input':
        out.push(b.reason === 'not_media_html' || b.reason === 'social_page' ? t('agentBlock.needUpload') : t('agentBlock.needInput'));
        break;
      case 'error':
        out.push(t('agentBlock.error', { reason: b.reason ?? '—' }));
        break;
    }
  }
  return out;
}

// Use-cases shared by screens: run a check, save it to local history, return the entry id.
import type { QorgauApi } from '../api/client';
import type { CheckResult } from '../api/types';
import { entryFromResult, type HistoryRepo } from '../db/history';

export async function checkUrlAndSave(api: QorgauApi, repo: HistoryRepo, url: string, network: boolean): Promise<string> {
  const result = await api.checkUrl(url.trim(), network);
  return saveResult(repo, result);
}

export async function saveResult(repo: HistoryRepo, result: CheckResult, fileName?: string): Promise<string> {
  const entry = entryFromResult(result, fileName);
  await repo.add(entry);
  return entry.id;
}

/** Client-side pre-check for QR / input display only. The server does the real validation. */
export function previewDomain(text: string): { isUrl: boolean; domain: string | null } {
  const s = text.trim();
  const m = /^(https?):\/\/([^/?#\s]+)/i.exec(s);
  if (!m) return { isUrl: false, domain: null };
  const authority = m[2];
  const host = authority.split('@').pop()!.replace(/:\d+$/, '').toLowerCase();
  return { isUrl: true, domain: host || null };
}

// Local history of checks. Stored ONLY on the device (SQLite); never sent to the server.
import type { CheckResult } from '../api/types';

export interface HistoryEntry {
  id: string;
  kind: 'url' | 'media';
  title: string;
  category: string;
  score: number | null;
  createdAt: number;
  demo: boolean;
  result: CheckResult;
}

export interface HistoryFilter {
  query?: string;
  kind?: 'url' | 'media' | 'all';
  category?: string | 'all';
  limit?: number;
}

export interface HistoryRepo {
  add(entry: HistoryEntry): Promise<void>;
  list(filter?: HistoryFilter): Promise<HistoryEntry[]>;
  get(id: string): Promise<HistoryEntry | null>;
  remove(id: string): Promise<void>;
  clear(): Promise<void>;
}

export function newId(): string {
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

export function titleFor(result: CheckResult, fileName?: string): string {
  if (result.kind === 'url') return result.normalized.host + (result.normalized.path || '');
  if (result.demo) return 'demo.mp4';
  return fileName || result.source_host || `${result.media_type}.${result.format}`;
}

export function entryFromResult(result: CheckResult, fileName?: string): HistoryEntry {
  return {
    id: newId(),
    kind: result.kind,
    title: titleFor(result, fileName),
    category: result.category,
    score: result.score,
    createdAt: Date.now(),
    demo: result.kind === 'media' ? !!result.demo : false,
    result: stripHeavy(result),
  };
}

/** Frame thumbnails are kept (small); nothing else heavy is returned by the API. */
function stripHeavy(result: CheckResult): CheckResult {
  return result;
}

export function matches(e: HistoryEntry, f: HistoryFilter = {}): boolean {
  if (f.kind && f.kind !== 'all' && e.kind !== f.kind) return false;
  if (f.category && f.category !== 'all' && e.category !== f.category) return false;
  if (f.query && !e.title.toLowerCase().includes(f.query.trim().toLowerCase())) return false;
  return true;
}

export class MemoryHistoryRepo implements HistoryRepo {
  private items: HistoryEntry[] = [];
  async add(entry: HistoryEntry) {
    this.items.unshift(entry);
  }
  async list(f: HistoryFilter = {}) {
    return this.items.filter((e) => matches(e, f)).slice(0, f.limit ?? 500);
  }
  async get(id: string) {
    return this.items.find((e) => e.id === id) ?? null;
  }
  async remove(id: string) {
    this.items = this.items.filter((e) => e.id !== id);
  }
  async clear() {
    this.items = [];
  }
}

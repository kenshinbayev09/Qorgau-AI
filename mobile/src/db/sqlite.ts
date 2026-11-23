import * as SQLite from 'expo-sqlite';

import type { HistoryEntry, HistoryFilter, HistoryRepo } from './history';

const DB_NAME = 'qorgau.db';
let dbPromise: Promise<SQLite.SQLiteDatabase> | null = null;

export function getDb(): Promise<SQLite.SQLiteDatabase> {
  if (!dbPromise) {
    dbPromise = (async () => {
      const db = await SQLite.openDatabaseAsync(DB_NAME);
      await db.execAsync(`
        PRAGMA journal_mode = WAL;
        CREATE TABLE IF NOT EXISTS history (
          id TEXT PRIMARY KEY NOT NULL,
          kind TEXT NOT NULL,
          title TEXT NOT NULL,
          category TEXT NOT NULL,
          score REAL,
          created_at INTEGER NOT NULL,
          demo INTEGER NOT NULL DEFAULT 0,
          result_json TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_history_created ON history(created_at DESC);
        CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY NOT NULL, value TEXT NOT NULL);
      `);
      return db;
    })();
  }
  return dbPromise;
}

interface Row {
  id: string;
  kind: 'url' | 'media';
  title: string;
  category: string;
  score: number | null;
  created_at: number;
  demo: number;
  result_json: string;
}

function toEntry(r: Row): HistoryEntry {
  return {
    id: r.id,
    kind: r.kind,
    title: r.title,
    category: r.category,
    score: r.score,
    createdAt: r.created_at,
    demo: !!r.demo,
    result: JSON.parse(r.result_json),
  };
}

export class SqliteHistoryRepo implements HistoryRepo {
  async add(e: HistoryEntry) {
    const db = await getDb();
    await db.runAsync(
      'INSERT OR REPLACE INTO history (id, kind, title, category, score, created_at, demo, result_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
      e.id, e.kind, e.title, e.category, e.score, e.createdAt, e.demo ? 1 : 0, JSON.stringify(e.result),
    );
  }

  async list(f: HistoryFilter = {}) {
    const db = await getDb();
    const where: string[] = [];
    const params: (string | number)[] = [];
    if (f.kind && f.kind !== 'all') {
      where.push('kind = ?');
      params.push(f.kind);
    }
    if (f.category && f.category !== 'all') {
      where.push('category = ?');
      params.push(f.category);
    }
    if (f.query && f.query.trim()) {
      where.push("LOWER(title) LIKE ? ESCAPE '\\'");
      params.push('%' + f.query.trim().toLowerCase().replace(/[\\%_]/g, (m) => '\\' + m) + '%');
    }
    const sql = `SELECT * FROM history ${where.length ? 'WHERE ' + where.join(' AND ') : ''} ORDER BY created_at DESC LIMIT ?`;
    params.push(f.limit ?? 500);
    const rows = await db.getAllAsync<Row>(sql, params);
    return rows.map(toEntry);
  }

  async get(id: string) {
    const db = await getDb();
    const row = await db.getFirstAsync<Row>('SELECT * FROM history WHERE id = ?', id);
    return row ? toEntry(row) : null;
  }

  async remove(id: string) {
    const db = await getDb();
    await db.runAsync('DELETE FROM history WHERE id = ?', id);
  }

  async clear() {
    const db = await getDb();
    await db.runAsync('DELETE FROM history');
  }
}

export async function loadSettingsRaw(): Promise<Record<string, string>> {
  const db = await getDb();
  const rows = await db.getAllAsync<{ key: string; value: string }>('SELECT key, value FROM settings');
  return Object.fromEntries(rows.map((r) => [r.key, r.value]));
}

export async function saveSetting(key: string, value: string): Promise<void> {
  const db = await getDb();
  await db.runAsync('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', key, value);
}

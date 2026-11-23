// Pure translation helpers (no React) so they can be unit-tested.
import { en } from './en';
import { kk } from './kk';
import { ru, type Translations } from './ru';

export type Lang = 'ru' | 'kk' | 'en';
export const LANGS: Lang[] = ['ru', 'kk', 'en'];
export const dictionaries: Record<Lang, Translations> = { ru, kk, en };

export function resolveLang(pref: string | null | undefined, deviceLangCode?: string | null): Lang {
  if (pref === 'ru' || pref === 'kk' || pref === 'en') return pref;
  const code = (deviceLangCode || '').toLowerCase();
  if (code.startsWith('kk')) return 'kk';
  if (code.startsWith('en')) return 'en';
  return 'ru';
}

export function lookup(dict: Translations, key: string): unknown {
  let cur: unknown = dict;
  for (const part of key.split('.')) {
    if (cur && typeof cur === 'object' && part in (cur as Record<string, unknown>)) {
      cur = (cur as Record<string, unknown>)[part];
    } else {
      return undefined;
    }
  }
  return cur;
}

export type Params = Record<string, string | number | null | undefined | string[]>;

export function interpolate(template: string, params?: Params): string {
  if (!params) return template;
  return template.replace(/\{(\w+)\}/g, (_, name: string) => {
    const v = params[name];
    if (v === undefined || v === null) return '—';
    return Array.isArray(v) ? v.join(', ') : String(v);
  });
}

export function translate(lang: Lang, key: string, params?: Params): string {
  const v = lookup(dictionaries[lang], key) ?? lookup(dictionaries.ru, key);
  return typeof v === 'string' ? interpolate(v, params) : key;
}

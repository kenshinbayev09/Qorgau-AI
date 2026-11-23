import { getLocales } from 'expo-localization';
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { Platform, useColorScheme } from 'react-native';

import { QorgauApi } from '../api/client';
import type { HistoryRepo } from '../db/history';
import { SqliteHistoryRepo, loadSettingsRaw, saveSetting } from '../db/sqlite';
import { dictionaries, resolveLang, translate, type Lang, type Params } from '../i18n/translate';
import { dark, light, type Palette } from '../theme/theme';

export type ThemePref = 'system' | 'dark' | 'light';
export type LangPref = 'system' | Lang;

export interface Settings {
  apiUrl: string;
  theme: ThemePref;
  lang: LangPref;
  networkChecks: boolean;
  demoMode: boolean;
  mediaConsent: boolean;
  fileUploadConsent: boolean; // согласие на отправку самих файлов в VirusTotal
  introSeen: boolean; // вступительный экран уже показан
  useLlm: boolean;
}

const defaultApi =
  process.env.EXPO_PUBLIC_API_URL ||
  (Platform.OS === 'android' ? 'http://10.0.2.2:8000' : 'http://localhost:8000');

export const DEFAULT_SETTINGS: Settings = {
  apiUrl: defaultApi,
  theme: 'system',
  lang: 'system',
  networkChecks: true,
  demoMode: false,
  mediaConsent: false,
  fileUploadConsent: false,
  introSeen: false,
  useLlm: false,
};

interface AppState {
  ready: boolean;
  settings: Settings;
  update: <K extends keyof Settings>(key: K, value: Settings[K]) => void;
  c: Palette;
  isDark: boolean;
  lang: Lang;
  t: (key: string, params?: Params) => string;
  tl: <T = unknown>(key: string) => T; // raw lookup for arrays/objects
  api: QorgauApi;
  repo: HistoryRepo;
  historyVersion: number;
  bumpHistory: () => void;
}

const Ctx = createContext<AppState | null>(null);
const repo = new SqliteHistoryRepo();

export function AppProvider({ children }: { children: ReactNode }) {
  const scheme = useColorScheme();
  const [settings, setSettings] = useState<Settings>(DEFAULT_SETTINGS);
  const [ready, setReady] = useState(false);
  const [historyVersion, setHistoryVersion] = useState(0);

  useEffect(() => {
    // Не даём белому экрану висеть, если база на телефоне отвечает долго.
    const guard = setTimeout(() => setReady(true), 3000);
    loadSettingsRaw()
      .then((raw) => {
        const s: Settings = { ...DEFAULT_SETTINGS };
        for (const [k, v] of Object.entries(raw)) {
          if (k in s) {
            try {
              (s as unknown as Record<string, unknown>)[k] = JSON.parse(v);
            } catch {
              /* ignore corrupted value */
            }
          }
        }
        setSettings(s);
      })
      .catch(() => undefined)
      .finally(() => {
        clearTimeout(guard);
        setReady(true);
      });
  }, []);

  const update = useCallback(<K extends keyof Settings>(key: K, value: Settings[K]) => {
    setSettings((prev) => ({ ...prev, [key]: value }));
    saveSetting(key, JSON.stringify(value)).catch(() => undefined);
  }, []);

  const isDark = settings.theme === 'dark' || (settings.theme === 'system' && scheme !== 'light');
  const deviceLang = getLocales()[0]?.languageCode ?? 'ru';
  const lang = resolveLang(settings.lang === 'system' ? null : settings.lang, deviceLang);

  const value = useMemo<AppState>(() => {
    const dict = dictionaries[lang];
    return {
      ready,
      settings,
      update,
      c: isDark ? dark : light,
      isDark,
      lang,
      t: (key, params) => translate(lang, key, params),
      tl: <T,>(key: string) => key.split('.').reduce<unknown>((o, k) => (o as Record<string, unknown>)?.[k], dict) as T,
      api: new QorgauApi(settings.apiUrl),
      repo,
      historyVersion,
      bumpHistory: () => setHistoryVersion((v) => v + 1),
    };
  }, [ready, settings, update, isDark, lang, historyVersion]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useApp(): AppState {
  const v = useContext(Ctx);
  if (!v) throw new Error('useApp must be used inside AppProvider');
  return v;
}

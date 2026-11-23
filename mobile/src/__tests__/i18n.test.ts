/// <reference types="jest" />
import { dictionaries, interpolate, LANGS, resolveLang, translate } from '../i18n/translate';

function leaves(obj: unknown, prefix = ''): [string, unknown][] {
  if (typeof obj === 'string') return [[prefix, obj]];
  if (Array.isArray(obj)) return [[prefix + '#len', obj.length], ...obj.flatMap((v, i) => leaves(v, `${prefix}.${i}`))];
  return Object.entries(obj as Record<string, unknown>).flatMap(([k, v]) => leaves(v, prefix ? `${prefix}.${k}` : k));
}

// Signal / advice / check ids emitted by the backend (backend/app/url_analysis/*.py).
const BACKEND_SIGNALS = [
  'ip_host', 'userinfo_in_url', 'homoglyph_brand', 'typosquat_brand', 'mixed_script', 'idn_domain', 'brand_in_subdomain',
  'brand_in_domain', 'brand_in_path', 'url_shortener', 'user_content_hosting', 'abused_tld', 'many_subdomains', 'many_hyphens',
  'long_url', 'suspicious_keywords', 'email_in_query', 'open_redirect_param', 'nonstandard_port', 'double_slash_path',
  'heavy_encoding', 'risky_download', 'no_tls', 'official_domain', 'redirect_to_internal', 'internal_address', 'invalid_redirect',
  'tls_invalid', 'domain_not_resolving', 'too_many_redirects', 'long_redirect_chain', 'cross_domain_redirect',
  'risky_final_destination', 'password_form', 'external_form_action', 'meta_refresh', 'reputation_match',
];
const BACKEND_ADVICE = ['verify_sender', 'https_not_guarantee', 'dont_enter_data', 'use_official_app', 'dont_open', 'report_link',
  'if_entered_act', 'check_letters', 'shortener_hidden', 'dont_install', 'password_only_official'];

describe('localisation', () => {
  const ruLeaves = new Map(leaves(dictionaries.ru));

  it.each(LANGS)('%s has every key of ru, non-empty, same placeholders', (lang) => {
    const l = new Map(leaves(dictionaries[lang]));
    for (const [key, value] of ruLeaves) {
      expect(l.has(key)).toBe(true);
      const other = l.get(key);
      if (typeof value === 'string') {
        expect(typeof other).toBe('string');
        expect((other as string).trim().length).toBeGreaterThan(0);
        const ph = (s: string) => (s.match(/\{\w+\}/g) ?? []).sort().join();
        expect([key, ph(other as string)]).toEqual([key, ph(value)]);
      } else {
        expect([key, other]).toEqual([key, value]); // array lengths
      }
    }
  });

  it.each(LANGS)('%s translates every backend signal and advice id', (lang) => {
    for (const id of BACKEND_SIGNALS) {
      expect(translate(lang, `signal.${id}.t`)).not.toBe(`signal.${id}.t`);
      expect(translate(lang, `signal.${id}.d`)).not.toBe(`signal.${id}.d`);
    }
    for (const id of BACKEND_ADVICE) expect(translate(lang, `advice.${id}`)).not.toBe(`advice.${id}`);
  });

  it('interpolates parameters and resolves language', () => {
    expect(interpolate('Домен {domain}, {x}', { domain: 'a.kz', x: ['b', 'c'] })).toBe('Домен a.kz, b, c');
    expect(interpolate('{missing}', {})).toBe('—');
    expect(resolveLang('system', 'kk')).toBe('kk');
    expect(resolveLang(null, 'de')).toBe('ru');
    expect(resolveLang('en', 'kk')).toBe('en');
  });
});

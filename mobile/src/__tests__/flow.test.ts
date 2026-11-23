/// <reference types="jest" />
import { ApiError, errorKey, QorgauApi } from '../api/client';
import type { UrlResult } from '../api/types';
import { MemoryHistoryRepo } from '../db/history';
import { translate, type Params } from '../i18n/translate';
import { checkUrlAndSave, previewDomain } from '../services/checks';
import { renderBlocks } from '../services/explain';

const urlResult: UrlResult = {
  kind: 'url',
  input: 'http://kaspi.kz.secure-login.xyz/verify',
  normalized: { scheme: 'http', host: 'kaspi.kz.secure-login.xyz', host_ascii: 'kaspi.kz.secure-login.xyz',
    registered_domain: 'secure-login.xyz', is_ip: false, path: '/verify', has_query: false },
  category: 'high',
  score: 0.88,
  score_components: { model: 0.97, rules: 0.79 },
  model: { status: 'loaded', version: 'url-ra-test', type: 'random_forest' },
  signals: [{ id: 'brand_in_subdomain', severity: 'high', weight: 0.6, params: { brand: 'kaspi', domain: 'secure-login.xyz' } }],
  checks: [{ id: 'redirects', status: 'skipped' }],
  redirects: null,
  advice: ['dont_open'],
  analyzed_at: '2026-11-08T10:00:00Z',
  duration_ms: 12,
};

function fakeFetch(status: number, body: unknown) {
  const calls: { url: string; init: RequestInit }[] = [];
  const impl = (async (url: string, init: RequestInit) => {
    calls.push({ url, init });
    return { ok: status < 400, status, json: async () => body } as Response;
  }) as unknown as typeof fetch;
  return { impl, calls };
}

describe('full scenario: link input -> check -> saved in history', () => {
  it('sends the link to the backend and stores the result locally', async () => {
    const { impl, calls } = fakeFetch(200, urlResult);
    const api = new QorgauApi('http://server:8000/', impl);
    const repo = new MemoryHistoryRepo();

    const id = await checkUrlAndSave(api, repo, '  http://kaspi.kz.secure-login.xyz/verify ', false);

    expect(calls[0].url).toBe('http://server:8000/api/v1/url/check');
    expect(JSON.parse(String(calls[0].init.body))).toEqual({ url: 'http://kaspi.kz.secure-login.xyz/verify', network: false });
    const saved = await repo.get(id);
    expect(saved?.category).toBe('high');
    expect(saved?.title).toBe('kaspi.kz.secure-login.xyz/verify');
    expect((await repo.list({ kind: 'url', category: 'high', query: 'secure-login' })).map((e) => e.id)).toEqual([id]);
    expect(await repo.list({ kind: 'media' })).toEqual([]);
    await repo.remove(id);
    expect(await repo.get(id)).toBeNull();
  });

  it('maps backend errors to localisable error keys and saves nothing', async () => {
    const { impl } = fakeFetch(422, { error: { code: 'invalid_url:unsupported_scheme' } });
    const repo = new MemoryHistoryRepo();
    await expect(checkUrlAndSave(new QorgauApi('http://s', impl), repo, 'javascript:x', true)).rejects.toMatchObject({
      code: 'invalid_url:unsupported_scheme',
    });
    expect(await repo.list()).toEqual([]);
    expect(errorKey('invalid_url:unsupported_scheme')).toBe('unsupported_scheme');
    expect(errorKey('model_unavailable')).toBe('model_unavailable');
    expect(errorKey('something_new')).toBe('server');
  });

  it('reports network failures as "network"', async () => {
    const impl = (async () => {
      throw new TypeError('Network request failed');
    }) as unknown as typeof fetch;
    await expect(new QorgauApi('http://s', impl).health()).rejects.toEqual(expect.any(ApiError));
    await expect(new QorgauApi('http://s', impl).health()).rejects.toMatchObject({ code: 'network' });
  });
});

describe('QR preview and agent explanation rendering', () => {
  it('extracts the real host for QR display', () => {
    expect(previewDomain('https://kaspi.kz@evil.top:8443/login')).toEqual({ isUrl: true, domain: 'evil.top' });
    expect(previewDomain('WIFI:S:home;T:WPA;P:secret;;')).toEqual({ isUrl: false, domain: null });
  });

  it('renders agent blocks from real result facts only', () => {
    const t = (k: string, p?: Params) => translate('ru', k, p);
    const lines = renderBlocks(
      [
        { type: 'verdict', kind: 'url', category: 'high', score: 0.88, domain: 'secure-login.xyz' },
        { type: 'reason', signal: 'brand_in_subdomain', severity: 'high' },
        { type: 'checks_not_done', checks: ['redirects'] },
        { type: 'note', id: 'llm_unavailable:AuthenticationError' },
      ],
      t,
      { brand_in_subdomain: { brand: 'kaspi', domain: 'secure-login.xyz' } },
    );
    expect(lines[0]).toContain('Высокий риск');
    expect(lines[0]).toContain('88/100');
    expect(lines[1]).toContain('kaspi');
    expect(lines[2]).toContain('перенаправлений');
    expect(lines[3]).toBe(translate('ru', 'agentNote.llm_unavailable'));
  });
});

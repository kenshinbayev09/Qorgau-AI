import { Platform } from 'react-native';
import type { AgentResponse, FileScanResult, Health, MediaResult, UrlResult } from './types';

export class ApiError extends Error {
  constructor(
    public code: string,
    public status: number,
    message?: string,
  ) {
    super(message || code);
  }
}

/** Map a backend error code like "invalid_url:unsupported_scheme" to an i18n key under `errors.` */
export function errorKey(code: string): string {
  const [head, sub] = code.split(':');
  if (head === 'invalid_url') return sub === 'unsupported_scheme' ? 'unsupported_scheme' : 'invalid_url';
  const known = [
    'network', 'timeout', 'unsupported_format', 'not_media_html', 'social_page', 'too_large', 'video_too_long',
    'image_too_large', 'unreadable', 'model_unavailable', 'blocked_url', 'download_failed', 'rate_limited',
    'processing_failed', 'empty_file', 'permission',
  ];
  return known.includes(head) ? head : 'server';
}

type FetchLike = typeof fetch;

/** В браузере выбранный файл — это blob-ссылка: превращаем её в настоящий File для FormData. На телефоне файл передаётся как есть. */
async function toFormFile(file: { uri: string; name: string; type: string; file?: Blob }): Promise<Blob> {
  if (file.file) return file.file; // на вебе выбор фото уже даёт настоящий File
  if (Platform.OS !== 'web') return file as unknown as Blob;
  const blob = await (await fetch(file.uri)).blob();
  return new File([blob], file.name, { type: file.type });
}

export class QorgauApi {
  constructor(
    private baseUrl: string,
    // Обёртка нужна: в браузере fetch нельзя вызывать как метод другого объекта (Illegal invocation).
    private fetchImpl: FetchLike = (input, init) => fetch(input, init),
  ) {}

  private url(path: string) {
    return this.baseUrl.replace(/\/+$/, '') + path;
  }

  private async request<T>(path: string, init: RequestInit, timeoutMs: number): Promise<T> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    let res: Response;
    try {
      res = await this.fetchImpl(this.url(path), { ...init, signal: controller.signal });
    } catch (e) {
      throw new ApiError(controller.signal.aborted ? 'timeout' : 'network', 0, String(e));
    } finally {
      clearTimeout(timer);
    }
    let body: unknown = null;
    try {
      body = await res.json();
    } catch {
      body = null;
    }
    if (!res.ok) {
      const code = (body as { error?: { code?: string } } | null)?.error?.code ?? (res.status === 504 ? 'timeout' : 'server');
      throw new ApiError(code, res.status);
    }
    return body as T;
  }

  health(): Promise<Health> {
    return this.request('/api/v1/health', { method: 'GET' }, 8000);
  }

  checkUrl(url: string, network: boolean): Promise<UrlResult> {
    return this.request('/api/v1/url/check', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url, network }),
    }, 30000);
  }

  checkMediaUrl(url: string): Promise<MediaResult> {
    return this.request('/api/v1/media/url', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url }),
    }, 150000);
  }

  /** Sends a file for a VirusTotal check. The file is uploaded only when allowUpload is true. */
  /** XMLHttpRequest: в React Native fetch не принимает файловые части FormData, XHR принимает. */
  async scanFile(file: { uri: string; name: string; type: string; file?: Blob }, allowUpload: boolean): Promise<FileScanResult> {
    const part = await toFormFile(file);
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open('POST', this.url('/api/v1/file/scan'));
      xhr.timeout = 180000;
      xhr.onload = () => {
        let body: unknown = null;
        try {
          body = JSON.parse(xhr.responseText);
        } catch {
          body = null;
        }
        if (xhr.status >= 200 && xhr.status < 300) resolve(body as FileScanResult);
        else reject(new ApiError((body as { error?: { code?: string } } | null)?.error?.code ?? 'server', xhr.status));
      };
      xhr.onerror = () => reject(new ApiError('network', 0));
      xhr.ontimeout = () => reject(new ApiError('timeout', 0));
      const form = new FormData();
      form.append('file', part, file.name);
      form.append('allow_upload', allowUpload ? 'true' : 'false');
      xhr.send(form);
    });
  }

  demoMedia(): Promise<MediaResult> {
    return this.request('/api/v1/demo/media', { method: 'GET' }, 8000);
  }

  runAgent(body: { text: string; attached_result?: unknown; lang: string; allow_network: boolean; use_llm: boolean }): Promise<AgentResponse> {
    return this.request('/api/v1/agent/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }, 160000);
  }

  /**
   * Upload with XMLHttpRequest so we can report the REAL phases: "uploading" until the
   * request body is fully sent, then "processing" while the server works. No fake percentages.
   */
  async uploadMedia(file: { uri: string; name: string; type: string; file?: Blob }, onPhase: (p: 'uploading' | 'processing') => void): Promise<MediaResult> {
    const part = await toFormFile(file);
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open('POST', this.url('/api/v1/media/upload'));
      xhr.timeout = 180000;
      onPhase('uploading');
      xhr.upload.onload = () => onPhase('processing');
      xhr.onload = () => {
        let body: unknown = null;
        try {
          body = JSON.parse(xhr.responseText);
        } catch {
          body = null;
        }
        if (xhr.status >= 200 && xhr.status < 300) resolve(body as MediaResult);
        else reject(new ApiError((body as { error?: { code?: string } } | null)?.error?.code ?? 'server', xhr.status));
      };
      xhr.onerror = () => reject(new ApiError('network', 0));
      xhr.ontimeout = () => reject(new ApiError('timeout', 0));
      const form = new FormData();
      // React Native FormData accepts { uri, name, type } file descriptors.
      form.append('file', part, file.name);
      xhr.send(form);
    });
  }
}

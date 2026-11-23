// Shapes returned by the Qorgau AI backend (see backend/app/*/service.py).
import type { Category } from '../theme/theme';

export interface Signal {
  id: string;
  severity: 'info' | 'low' | 'medium' | 'high';
  weight: number;
  params: Record<string, string | number | boolean | string[] | null>;
}

export interface CheckItem {
  id: string;
  status: 'done' | 'unavailable' | 'skipped' | 'disabled' | 'failed' | 'stopped';
  detail?: string | null;
}

export interface Hop {
  url: string;
  host: string;
  ip: string | null;
  status: number | null;
  location: string | null;
  blocked_reason: string | null;
  elapsed_ms: number;
}

export interface UrlResult {
  kind: 'url';
  input: string;
  normalized: {
    scheme: string;
    host: string;
    host_ascii: string;
    registered_domain: string;
    is_ip: boolean;
    path: string;
    has_query: boolean;
  };
  category: Category;
  score: number | null;
  score_components: { model: number | null; rules: number };
  model: { status: string; version: string | null; type: string | null };
  signals: Signal[];
  checks: CheckItem[];
  redirects: { hops: Hop[]; error_code: string | null; final_url: string | null } | null;
  advice: string[];
  analyzed_at: string;
  duration_ms: number;
}

export interface Frame {
  index: number;
  t_sec: number;
  has_face: boolean;
  score: number | null;
  thumb: string | null;
}

export interface MediaResult {
  kind: 'media';
  demo: boolean;
  source: 'upload' | 'url' | 'demo';
  source_host?: string;
  media_type: 'image' | 'video';
  format: string;
  status: 'done' | 'insufficient';
  category: Category;
  score: number | null;
  reason: string | null;
  meta: Record<string, number>;
  frames: Frame[];
  top_frames: number[];
  aggregate: {
    method: string;
    frames_sampled: number;
    frames_with_face: number;
    median: number | null;
    mean: number | null;
    max: number | null;
    share_over_0_5: number | null;
  };
  stages: { id: string; status: string; ms: number }[];
  limitations: string[];
  model: { name: string; status: string; version: string | null; license: string | null };
  duration_ms?: number;
}

export type CheckResult = UrlResult | MediaResult;

export interface FileScanResult {
  status: 'done' | 'disabled' | 'upload_required' | 'too_large' | 'rate_limited' | 'timeout' | 'failed';
  sha256: string;
  permalink: string;
  stats: { malicious?: number; suspicious?: number; undetected?: number; harmless?: number } | null;
  verdict: 'clean' | 'suspicious' | 'malicious' | null;
  source: 'known' | 'uploaded' | null;
  reason: string | null;
  allow_upload: boolean;
}

export interface TraceStep {
  step: number;
  state: string;
  action: string;
  detail: Record<string, unknown>;
  ms: number;
}

export type ExplanationBlock =
  | { type: 'verdict'; kind: 'url' | 'media' | null; category: Category; score: number | null; domain?: string | null }
  | { type: 'reason'; signal: string; severity: string }
  | { type: 'media_summary'; frames_sampled?: number; frames_with_face?: number; max_frame_score?: number | null; reason?: string | null }
  | { type: 'checks_not_done'; checks: string[] }
  | { type: 'advice'; id: string }
  | { type: 'note'; id: string }
  | { type: 'need_input'; reason: string | null }
  | { type: 'error'; reason: string | null };

export interface AgentResponse {
  state: string;
  input_type: string;
  tool_used: string | null;
  result: CheckResult | null;
  error: string | null;
  explanation: { source: string; blocks: ExplanationBlock[]; text: string | null };
  actions: string[];
  notes: string[];
  trace: TraceStep[];
  tools: { name: string; available: boolean; reason: string | null }[];
}

export interface Health {
  status: string;
  version: string;
  url_model: { status: string; version: string | null; type: string | null };
  deepfake_model: { status: string; name: string; version: string | null; license: string };
  network_checks: boolean;
  external_services: { safe_browsing: boolean; llm_explanations: boolean };
  limits: { max_upload_mb: number; max_video_seconds: number; max_video_frames: number };
}

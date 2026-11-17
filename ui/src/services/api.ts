/**
 * REST client for the Kiwis FastAPI backend.
 * Every function resolves to the unwrapped `data` of the `{ success, data }` envelope
 * and rejects with an `ApiError` (status, code, message) on failure.
 */

import type {
  ApiResponse,
  BackendConfig,
  CostSnapshot,
  CreateResearchRequest,
  PaperResult,
  PipelineJob,
  ResearchStep,
  ReviewScores,
  SwarmHealth,
  AgentNode,
  TerminalLog,
  Artifact,
  UpdatePipelineStatusRequest,
} from '@/types/api';

export const API_BASE: string = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';
/** Origin of the backend (used for absolute links such as PDFs). */
export const API_ORIGIN = new URL(API_BASE, window.location.href).origin;

export class ApiError extends Error {
  constructor(
    public code: string,
    message: string,
    public status?: number,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

async function request<T>(path: string, options: RequestInit = {}, timeoutMs = 30_000): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      ...options,
      signal: controller.signal,
      headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) },
    });
    let body: (ApiResponse<T> & { code?: string; message?: string }) | null = null;
    try {
      body = await res.json();
    } catch {
      /* non-JSON response */
    }
    if (!res.ok || body?.success === false) {
      throw new ApiError(
        body?.code ?? body?.error?.code ?? `HTTP_${res.status}`,
        body?.message ?? body?.error?.message ?? `Request failed (${res.status})`,
        res.status,
      );
    }
    return body?.data as T;
  } catch (e) {
    if (e instanceof ApiError) throw e;
    if (e instanceof Error && e.name === 'AbortError') throw new ApiError('TIMEOUT', 'The request timed out');
    throw new ApiError('NETWORK', 'Cannot reach the Kiwis backend. Is `kiwis serve` running?');
  } finally {
    clearTimeout(timer);
  }
}

const json = (method: string, body?: unknown): RequestInit => ({
  method,
  body: body === undefined ? undefined : JSON.stringify(body),
});

export const pipelineApi = {
  list: () => request<PipelineJob[]>('/pipelines'),
  get: (id: string) => request<PipelineJob>(`/pipelines/${id}`),
  create: (body: CreateResearchRequest) =>
    request<{ pipelineId: string; status: string }>('/pipelines', json('POST', body)),
  updateStatus: (id: string, body: UpdatePipelineStatusRequest) =>
    request<PipelineJob>(`/pipelines/${id}/status`, json('PATCH', body)),
  remove: (id: string) => request<null>(`/pipelines/${id}`, json('DELETE')),
  steps: (id: string) => request<ResearchStep[]>(`/pipelines/${id}/steps`),
  logs: (id: string, limit = 300) => request<(TerminalLog & { pipelineId: string })[]>(`/pipelines/${id}/logs?limit=${limit}`),
  reexecute: (pipelineId: string, stepNum: number, cascade = false) =>
    request<{ success: boolean; newLogId: string }>('/pipelines/reexecute', json('POST', { pipelineId, stepNum, cascade })),
};

export const swarmApi = {
  health: () => request<SwarmHealth>('/swarm/health'),
  agents: () => request<AgentNode[]>('/swarm/agents'),
};

export const costApi = {
  snapshot: (pipelineId?: string) =>
    request<CostSnapshot>(`/costs${pipelineId ? `?pipeline_id=${pipelineId}` : ''}`),
  breakdown: (pipelineId: string) =>
    request<Record<string, { tokens: number; costUsd: string }>>(`/costs/breakdown/${pipelineId}`),
};

export const resultsApi = {
  paper: (id: string) => request<PaperResult>(`/results/${id}/paper`),
  review: (id: string) => request<ReviewScores>(`/results/${id}/review`),
  artifacts: (id: string) => request<Artifact[]>(`/results/${id}/artifacts`),
  artifactUrl: (id: string, artifactId: string) =>
    `${API_BASE}/results/${id}/artifacts/${encodeURIComponent(artifactId)}/download`,
  artifactText: async (id: string, artifactId: string): Promise<string> => {
    const res = await fetch(resultsApi.artifactUrl(id, artifactId));
    if (!res.ok) throw new ApiError(`HTTP_${res.status}`, 'Artifact not available', res.status);
    return res.text();
  },
};

export interface PaperHit {
  id: string;
  title?: string;
  authors?: string[];
  year?: number;
  summary?: string;
  source?: string;
}

export const searchApi = {
  papers: (query: string, n = 20) =>
    request<PaperHit[]>(`/search/papers?q=${encodeURIComponent(query)}&n=${n}`, {}, 60_000),
};

export interface StorageInfo {
  jobs: number;
  finished: number;
  totalBytes: number;
  items: { id: string; title: string; status: string; updatedAt: string; bytes: number }[];
  retention: { max_age_days: number | null; max_jobs: number | null };
}

export interface CleanupResult {
  dryRun: boolean;
  deleted: number;
  freedBytes: number;
  items: { id: string; title: string; bytes: number }[];
}

export const storageApi = {
  info: () => request<StorageInfo>('/storage'),
  cleanup: (body: { olderThanDays?: number; keepLast?: number; dryRun?: boolean }) =>
    request<CleanupResult>('/storage/cleanup', json('POST', body)),
};

export const systemApi = {
  config: () => request<BackendConfig>('/config'),
  health: async () => {
    const res = await fetch(`${API_ORIGIN}/health`);
    if (!res.ok) throw new ApiError(`HTTP_${res.status}`, 'Backend not healthy', res.status);
    return (await res.json()) as { status: string; version: string };
  },
};

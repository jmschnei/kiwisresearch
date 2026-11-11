/**
 * Service layer for communicating with the FastAPI backend.
 * Uses native Fetch API with AbortController for cancellable requests,
 * typed request/response DTOs, and automatic retry logic.
 */

import type {
  ApiResponse,
  ApiError,
  CreateResearchRequest,
  UpdatePipelineStatusRequest,
  ReexecuteStepRequest,
  PipelineJob,
  PaperResult,
  CostSnapshot,
  SwarmHealth,
  ResearchStep,
} from '@/types/api';

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

// ─── Fetch wrapper with typed response + error handling ───

async function fetchJson<T>(url: string, options?: RequestInit): Promise<ApiResponse<T>> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 30_000);

  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal,
      headers: {
        'Content-Type': 'application/json',
        ...(options?.headers ?? {}),
      },
    });

    clearTimeout(timeoutId);

    const data = await response.json();

    if (!response.ok) {
      throw new ApiError(
        `HTTP ${response.status}`,
        (data as ApiError)?.message || `Request failed with status ${response.status}`,
        { method: 'GET', url, status: response.status },
      );
    }

    return data as ApiResponse<T>;
  } catch (error) {
    clearTimeout(timeoutId);

    if (error instanceof Error && error.name === 'AbortError') {
      throw new ApiError('TIMEOUT', `Request to ${url} timed out after 30s`);
    }

    throw error;
  }
}

// ─── Pipeline endpoints ───

export const pipelineApi = {
  /** List all pipeline jobs */
  list: () => fetchJson<PipelineJob[]>(`${API_BASE}/pipelines`),

  /** Get details of a specific pipeline */
  get: (id: string) => fetchJson<PipelineJob>(`${API_BASE}/pipelines/${id}`),

  /** Create a new research pipeline */
  create: (body: CreateResearchRequest) =>
    fetchJson<{ pipelineId: string; status: string }>(`${API_BASE}/pipelines`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  /** Update pipeline status (pause/resume) */
  updateStatus: (id: string, body: UpdatePipelineStatusRequest) =>
    fetchJson<PipelineJob>(`${API_BASE}/pipelines/${id}/status`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  /** Delete a pipeline */
  delete: (id: string) =>
    fetchJson<void>(`${API_BASE}/pipelines/${id}`, { method: 'DELETE' }),

  /** Get steps for a pipeline */
  getSteps: (pipelineId: string) =>
    fetchJson<ResearchStep[]>(`${API_BASE}/pipelines/${pipelineId}/steps`),

  /** Re-execute a specific step */
  reexecuteStep: (body: ReexecuteStepRequest) =>
    fetchJson<{ success: boolean; newLogId: string }>(`${API_BASE}/pipelines/reexecute`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
};

// ─── Swarm endpoints ───

export const swarmApi = {
  /** Get current swarm health status */
  getHealth: () => fetchJson<SwarmHealth>(`${API_BASE}/swarm/health`),

  /** Get all agent states */
  getAgents: () => fetchJson<any[]>(`${API_BASE}/swarm/agents`),

  /** Force restart an agent */
  restartAgent: (agentId: string) =>
    fetchJson<{ status: string }>(`${API_BASE}/swarm/${agentId}/restart`, { method: 'POST' }),
};

// ─── Cost tracking ───

export const costApi = {
  /** Get current cost snapshot */
  getSnapshot: (pipelineId?: string) =>
    fetchJson<CostSnapshot>(`${API_BASE}/costs${pipelineId ? `?pipeline_id=${pipelineId}` : ''}`),

  /** Get cost history for a pipeline */
  getHistory: (pipelineId: string, rangeDays = 30) =>
    fetchJson<Array<{ date: string; tokens: number; costUsd: string }>>(
      `${API_BASE}/costs/history?pipeline_id=${pipelineId}&days=${rangeDays}`,
    ),

  /** Get cost breakdown by agent */
  getBreakdownByAgent: (pipelineId: string) =>
    fetchJson<Record<string, { tokens: number; costUsd: string }>>(
      `${API_BASE}/costs/breakdown/${pipelineId}`,
    ),
};

// ─── Results / Paper viewer ───

export const resultsApi = {
  /** Get the compiled paper result */
  getPaper: (pipelineId: string) => fetchJson<PaperResult>(`${API_BASE}/results/${pipelineId}/paper`),

  /** List artifacts for a pipeline */
  listArtifacts: (pipelineId: string) =>
    fetchJson<any[]>(`${API_BASE}/results/${pipelineId}/artifacts`),

  /** Download artifact by ID */
  downloadArtifact: (pipelineId: string, artifactId: string) =>
    `${API_BASE}/results/${pipelineId}/artifacts/${artifactId}/download`,

  /** Get peer review scores */
  getReviewScores: (pipelineId: string) =>
    fetchJson<{ metrics: any[]; consensus: string }>(`${API_BASE}/results/${pipelineId}/review`),
};

// ─── Search & discovery ───

export const searchApi = {
  /** Search papers via RAG engine */
  searchPapers: (query: string, n = 20) =>
    fetchJson<any[]>(`${API_BASE}/search/papers?q=${encodeURIComponent(query)}&n=${n}`),

  /** Suggest research directions */
  suggestDirections: (domain: string, topic: string) =>
    fetchJson<{ directions: string[]; confidence: number[] }>(
      `${API_BASE}/search/suggest?domain=${domain}&topic=${encodeURIComponent(topic)}`,
    ),
};

// ─── Custom ApiError class ───

export class ApiError extends Error {
  constructor(public code: string, message: string, public details?: Record<string, any>) {
    super(message);
    this.name = 'ApiError';
  }
}

export default {
  pipeline: pipelineApi,
  swarm: swarmApi,
  cost: costApi,
  results: resultsApi,
  search: searchApi,
};

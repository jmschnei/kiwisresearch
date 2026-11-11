/**
 * React Query hooks for all API endpoints.
 * Provides automatic caching, background refetching, and optimistic updates.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import * as api from '@/services/api';
import type { CreateResearchRequest, PipelineJob, ResearchStep } from '@/types/api';

// ─── Query Keys ───

export const queryKeys = {
  pipelines: ['pipelines'] as const,
  pipeline: (id: string) => ['pipeline', id] as const,
  swarmHealth: ['swarm', 'health'] as const,
  agents: ['agents'] as const,
  costs: (id?: string) => ['costs', id ?? 'global'] as const,
  paperResult: (id: string) => ['paper', id] as const,
  reviewScores: (id: string) => ['review', id] as const,
  artifacts: (id: string) => ['artifacts', id] as const,
  steps: (pipelineId: string) => ['steps', pipelineId] as const,
};

// ─── Queries ───

export function usePipelines() {
  return useQuery({
    queryKey: queryKeys.pipelines,
    queryFn: () => api.pipeline.list(),
    refetchInterval: Number(import.meta.env.VITE_POLL_INTERVAL) || 5000,
  });
}

export function usePipeline(id: string | null) {
  return useQuery({
    queryKey: queryKeys.pipeline(id!),
    queryFn: () => api.pipeline.get(id!),
    enabled: !!id,
  });
}

export function useSwarmHealth() {
  return useQuery({
    queryKey: queryKeys.swarmHealth,
    queryFn: () => api.swarmApi.getHealth(),
    refetchInterval: 5000,
  });
}

export function useCostSnapshot(pipelineId?: string) {
  return useQuery({
    queryKey: queryKeys.costs(pipelineId),
    queryFn: () => api.costApi.getSnapshot(pipelineId),
    refetchInterval: 2000,
  });
}

export function usePipelineSteps(pipelineId: string | null) {
  return useQuery({
    queryKey: queryKeys.steps(pipelineId!),
    queryFn: () => api.pipeline.getSteps(pipelineId!),
    enabled: !!pipelineId,
    refetchInterval: 3000,
  });
}

export function usePaperResult(pipelineId: string | null) {
  return useQuery({
    queryKey: queryKeys.paperResult(pipelineId!),
    queryFn: () => api.resultsApi.getPaper(pipelineId!),
    enabled: !!pipelineId,
  });
}

// ─── Mutations ───

export function useCreateResearch() {
  const qc = useQueryClient();

  return useMutation({
    mutationFn: (body: CreateResearchRequest) => api.pipeline.create(body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.pipelines });
    },
  });
}

export function useReexecuteStep() {
  const qc = useQueryClient();

  return useMutation({
    mutationFn: (body: Parameters<typeof api.pipeline.reexecuteStep>[0]) =>
      api.pipeline.reexecuteStep(body),
    onSuccess: (_data, variables) => {
      qc.invalidateQueries({ queryKey: queryKeys.steps(variables.pipelineId) });
    },
  });
}

export function useUpdatePipelineStatus() {
  const qc = useQueryClient();

  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: Parameters<typeof api.pipeline.updateStatus>[1] }) =>
      api.pipeline.updateStatus(id, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.pipelines });
    },
  });
}

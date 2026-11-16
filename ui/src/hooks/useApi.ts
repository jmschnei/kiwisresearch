/**
 * React Query hooks. Live updates arrive through the WebSocket (see useLiveSync), which
 * invalidates these queries; the refetch intervals below are only a fallback.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { costApi, pipelineApi, resultsApi, searchApi, swarmApi, systemApi, ApiError } from '@/services/api';
import type { CreateResearchRequest, PipelineStatus } from '@/types/api';
import { useDashboardStore } from '@/store/dashboard';

export const queryKeys = {
  pipelines: ['pipelines'] as const,
  pipeline: (id: string) => ['pipeline', id] as const,
  steps: (id: string) => ['steps', id] as const,
  agents: ['agents'] as const,
  health: ['swarm-health'] as const,
  costs: (id?: string) => ['costs', id ?? 'global'] as const,
  breakdown: (id: string) => ['breakdown', id] as const,
  paper: (id: string) => ['paper', id] as const,
  review: (id: string) => ['review', id] as const,
  artifacts: (id: string) => ['artifacts', id] as const,
  config: ['config'] as const,
  backend: ['backend-health'] as const,
};

const FALLBACK_POLL = 10_000;

export const usePipelines = () =>
  useQuery({ queryKey: queryKeys.pipelines, queryFn: pipelineApi.list, refetchInterval: FALLBACK_POLL });

export const usePipeline = (id: string | undefined) =>
  useQuery({
    queryKey: queryKeys.pipeline(id ?? ''),
    queryFn: () => pipelineApi.get(id!),
    enabled: !!id,
    refetchInterval: FALLBACK_POLL,
    retry: (n, e) => !(e instanceof ApiError && e.status === 404) && n < 2,
  });

export const usePipelineSteps = (id: string | undefined) =>
  useQuery({
    queryKey: queryKeys.steps(id ?? ''),
    queryFn: () => pipelineApi.steps(id!),
    enabled: !!id,
    refetchInterval: FALLBACK_POLL,
  });

export const useAgents = () =>
  useQuery({ queryKey: queryKeys.agents, queryFn: swarmApi.agents, refetchInterval: FALLBACK_POLL });

export const useSwarmHealth = () =>
  useQuery({ queryKey: queryKeys.health, queryFn: swarmApi.health, refetchInterval: FALLBACK_POLL });

export const useCosts = (pipelineId?: string) =>
  useQuery({
    queryKey: queryKeys.costs(pipelineId),
    queryFn: () => costApi.snapshot(pipelineId),
    refetchInterval: FALLBACK_POLL,
  });

export const useCostBreakdown = (id: string | undefined) =>
  useQuery({ queryKey: queryKeys.breakdown(id ?? ''), queryFn: () => costApi.breakdown(id!), enabled: !!id });

export const usePaper = (id: string | undefined, enabled = true) =>
  useQuery({
    queryKey: queryKeys.paper(id ?? ''),
    queryFn: () => resultsApi.paper(id!),
    enabled: !!id && enabled,
    retry: false,
  });

export const useReview = (id: string | undefined, enabled = true) =>
  useQuery({
    queryKey: queryKeys.review(id ?? ''),
    queryFn: () => resultsApi.review(id!),
    enabled: !!id && enabled,
    retry: false,
  });

export const useArtifacts = (id: string | undefined) =>
  useQuery({ queryKey: queryKeys.artifacts(id ?? ''), queryFn: () => resultsApi.artifacts(id!), enabled: !!id });

export const useBackendConfig = () =>
  useQuery({ queryKey: queryKeys.config, queryFn: systemApi.config, retry: false });

export const useBackendHealth = () =>
  useQuery({ queryKey: queryKeys.backend, queryFn: systemApi.health, refetchInterval: 5000, retry: false });

export const usePaperSearch = (query: string) =>
  useQuery({
    queryKey: ['paper-search', query],
    queryFn: () => searchApi.papers(query, 20),
    enabled: query.trim().length > 0,
    staleTime: 5 * 60_000,
    retry: false,
  });

// ── Mutations ──

function useErrorToast() {
  const push = useDashboardStore((s) => s.pushToast);
  return (e: unknown) => push('error', e instanceof Error ? e.message : 'Unexpected error');
}

export function useCreateResearch() {
  const qc = useQueryClient();
  const onError = useErrorToast();
  return useMutation({
    mutationFn: (body: CreateResearchRequest) => pipelineApi.create(body),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.pipelines }),
    onError,
  });
}

export function useSetPipelineStatus() {
  const qc = useQueryClient();
  const onError = useErrorToast();
  return useMutation({
    mutationFn: ({ id, status, reason }: { id: string; status: PipelineStatus; reason?: string }) =>
      pipelineApi.updateStatus(id, { pipelineId: id, status, reason }),
    onSuccess: (_d, v) => {
      qc.invalidateQueries({ queryKey: queryKeys.pipelines });
      qc.invalidateQueries({ queryKey: queryKeys.pipeline(v.id) });
    },
    onError,
  });
}

export function useDeletePipeline() {
  const qc = useQueryClient();
  const onError = useErrorToast();
  return useMutation({
    mutationFn: (id: string) => pipelineApi.remove(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.pipelines }),
    onError,
  });
}

export function useReexecuteStep() {
  const qc = useQueryClient();
  const onError = useErrorToast();
  const push = useDashboardStore((s) => s.pushToast);
  return useMutation({
    mutationFn: ({ id, step }: { id: string; step: number }) => pipelineApi.reexecute(id, step),
    onSuccess: (_d, v) => {
      push('info', `Re-ejecutando el paso ${v.step}`);
      qc.invalidateQueries({ queryKey: queryKeys.steps(v.id) });
      qc.invalidateQueries({ queryKey: queryKeys.pipeline(v.id) });
    },
    onError,
  });
}

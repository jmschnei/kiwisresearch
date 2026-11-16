import type { PipelineStatus, ReviewConsensus } from '@/types/api';

export const formatTokens = (n: number): string =>
  n >= 1_000_000 ? `${(n / 1_000_000).toFixed(1)}M` : n >= 1_000 ? `${(n / 1_000).toFixed(1)}K` : String(n);

export const formatUsd = (v: string | number): string => `$${Number(v).toFixed(Number(v) >= 1 ? 2 : 4)}`;

export const timeAgo = (iso: string): string => {
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return 'hace un momento';
  if (s < 3600) return `hace ${Math.floor(s / 60)} min`;
  if (s < 86400) return `hace ${Math.floor(s / 3600)} h`;
  return `hace ${Math.floor(s / 86400)} d`;
};

export type BadgeVariant = 'blue' | 'cyan' | 'green' | 'yellow' | 'orange' | 'red' | 'purple' | 'pink' | 'gray';

export const STATUS_BADGE: Record<PipelineStatus, { label: string; variant: BadgeVariant; bar: string }> = {
  active: { label: 'En curso', variant: 'blue', bar: 'blue' },
  paused: { label: 'Pausada', variant: 'yellow', bar: 'yellow' },
  completed: { label: 'Completada', variant: 'green', bar: 'green' },
  failed: { label: 'Fallida', variant: 'red', bar: 'red' },
};

export const CONSENSUS_LABEL: Record<ReviewConsensus, { label: string; variant: BadgeVariant }> = {
  accepted: { label: 'Aceptado', variant: 'green' },
  weak_accept: { label: 'Aceptación débil', variant: 'cyan' },
  borderline: { label: 'Dudoso', variant: 'yellow' },
  rejected: { label: 'Rechazado', variant: 'red' },
};

export const RESEARCH_TYPES: { value: string; label: string }[] = [
  { value: 'paper', label: '📝 Artículo completo' },
  { value: 'survey', label: '📚 Survey sistemática' },
  { value: 'exploration', label: '🔍 Exploración de líneas' },
  { value: 'experiment', label: '🧪 Diseño experimental' },
  { value: 'benchmark', label: '📊 Benchmark' },
];

export const RESEARCH_DOMAINS = ['ml', 'nlp', 'cv', 'graphs', 'rl', 'privacy', 'multimodal', 'edge'];

export const DEPTH_LEVELS: { value: 'fast' | 'standard' | 'deep' | 'max'; label: string }[] = [
  { value: 'fast', label: '⚡ Rápido' },
  { value: 'standard', label: '📏 Estándar' },
  { value: 'deep', label: '🔬 Profundo' },
  { value: 'max', label: '💎 Máximo' },
];

/** Extra review rounds per depth level on top of the backend's configured rounds (fast = a single review). */
const EXTRA_ROUNDS = { fast: null, standard: 0, deep: 1, max: 2 } as const;

export const reviewRoundsFor = (level: keyof typeof EXTRA_ROUNDS, baseRounds: number): number => {
  const extra = EXTRA_ROUNDS[level];
  return extra === null ? 1 : baseRounds + extra;
};

export const depthOptions = (baseRounds = 2) =>
  DEPTH_LEVELS.map((d) => {
    const n = reviewRoundsFor(d.value, baseRounds);
    return { value: d.value, label: `${d.label} · ${n === 1 ? 'una revisión' : `hasta ${n} rondas de revisión`}` };
  });

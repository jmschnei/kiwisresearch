import { useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Pause, Play, Trash2 } from 'lucide-react';
import { Badge } from '@/components/common/Badge';
import { ProgressBar } from '@/components/common/ProgressBar';
import { ErrorBox, Spinner } from '@/components/common/Spinner';
import { useAgents, useCosts, useDeletePipeline, usePipelines, useSetPipelineStatus } from '@/hooks/useApi';
import { formatTokens, formatUsd, STATUS_BADGE, timeAgo } from '@/lib/format';
import type { PipelineStatus } from '@/types/api';

const FILTERS: { key: 'all' | PipelineStatus; label: string }[] = [
  { key: 'all', label: 'Todas' },
  { key: 'active', label: 'En curso' },
  { key: 'paused', label: 'Pausadas' },
  { key: 'completed', label: 'Completadas' },
  { key: 'failed', label: 'Fallidas' },
];

const AGENT_DOT: Record<string, string> = {
  thinking: 'bg-cyber-purple animate-pulse', executing: 'bg-cyber-green animate-pulse', reviewing: 'bg-cyber-red animate-pulse',
  waiting: 'bg-cyber-yellow', idle: 'bg-gray-600',
};

export function PipelinesPage() {
  const navigate = useNavigate();
  const { data: pipelines, isLoading, error, refetch } = usePipelines();
  const { data: agents } = useAgents();
  const { data: cost } = useCosts();
  const setStatus = useSetPipelineStatus();
  const remove = useDeletePipeline();
  const [filter, setFilter] = useState<'all' | PipelineStatus>('all');
  const [query, setQuery] = useState('');

  const counts = useMemo(() => {
    const c: Record<string, number> = { all: pipelines?.length ?? 0 };
    pipelines?.forEach((p) => (c[p.status] = (c[p.status] ?? 0) + 1));
    return c;
  }, [pipelines]);

  const shown = (pipelines ?? []).filter(
    (p) => (filter === 'all' || p.status === filter) && p.name.toLowerCase().includes(query.toLowerCase()),
  );

  return (
    <div className="page-scroll">
      <div className="max-w-6xl mx-auto px-6 py-8 space-y-6">
        <div className="flex items-end justify-between gap-4 flex-wrap">
          <div>
            <h1 className="text-2xl font-bold text-gray-100">Investigaciones</h1>
            <p className="text-sm text-gray-500">Todas las ejecuciones del enjambre de agentes.</p>
          </div>
          <Link to="/" className="btn-primary">+ Nueva investigación</Link>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[
            { label: 'En curso', value: String(counts.active ?? 0), color: 'text-cyber-blue' },
            { label: 'Completadas', value: String(counts.completed ?? 0), color: 'text-cyber-green' },
            { label: 'Tokens (est.)', value: formatTokens(cost?.tokensUsed ?? 0), color: 'text-cyber-cyan' },
            { label: 'Coste (est.)', value: formatUsd(cost?.costUsd ?? 0), color: 'text-cyber-yellow' },
          ].map((m) => (
            <div key={m.label} className="metric-card">
              <div className="text-[10px] text-gray-500 uppercase tracking-wider">{m.label}</div>
              <div className={`text-2xl font-bold terminal-font mt-1 ${m.color}`}>{m.value}</div>
            </div>
          ))}
        </div>

        {agents && (
          <div className="glass-panel px-5 py-3 flex flex-wrap items-center gap-x-6 gap-y-2">
            <span className="text-[11px] text-gray-500 uppercase tracking-wider">Enjambre</span>
            {agents.map((a) => (
              <span key={a.id} className="flex items-center gap-2 text-xs text-gray-400" title={a.status}>
                <span className={`w-2 h-2 rounded-full ${AGENT_DOT[a.status]}`} />
                {a.icon} {a.name}
              </span>
            ))}
          </div>
        )}

        <div className="flex items-center gap-3 flex-wrap">
          <div className="flex gap-1.5">
            {FILTERS.map((f) => (
              <button key={f.key} onClick={() => setFilter(f.key)}
                className={`px-3 py-1.5 text-xs rounded-lg border transition-all font-medium ${
                  filter === f.key ? 'bg-dark-hover text-cyber-blue border-cyber-blue/40' : 'text-gray-500 border-dark-primary/40 hover:text-gray-300'
                }`}>
                {f.label} <span className="text-gray-600">{counts[f.key] ?? 0}</span>
              </button>
            ))}
          </div>
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Buscar…" aria-label="Buscar investigaciones"
            className="form-field-input !w-56 ml-auto" />
        </div>

        {isLoading && <Spinner label="Cargando investigaciones…" />}
        {error && <ErrorBox message={(error as Error).message} onRetry={() => refetch()} />}

        <div className="space-y-3">
          {shown.map((p) => (
            <div key={p.id} onClick={() => navigate(`/pipelines/${p.id}`)} className={`pipeline-card ${p.status} !p-5`}>
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <div className="flex items-center gap-3 mb-1">
                    <span className="font-semibold text-gray-100 truncate">{p.name}</span>
                    <Badge label={STATUS_BADGE[p.status].label} variant={STATUS_BADGE[p.status].variant} dot />
                  </div>
                  <div className="text-[11px] text-gray-500">
                    {p.type} · {p.domain.toUpperCase()} · {timeAgo(p.createdAt)} · {p.elapsedTime} · {p.tokensUsed} tok · {formatUsd(p.spentUsd)}
                  </div>
                  {p.error && p.status === 'failed' && <div className="text-[11px] text-cyber-red mt-1 truncate">{p.error}</div>}
                </div>
                <div className="flex items-center gap-1.5 shrink-0" onClick={(e) => e.stopPropagation()}>
                  {p.status === 'active' && (
                    <button title="Pausar" aria-label="Pausar" onClick={() => setStatus.mutate({ id: p.id, status: 'paused' })} className="btn-ghost !p-2"><Pause className="w-4 h-4" /></button>
                  )}
                  {p.status === 'paused' && (
                    <button title="Reanudar" aria-label="Reanudar" onClick={() => setStatus.mutate({ id: p.id, status: 'active' })} className="btn-ghost !p-2"><Play className="w-4 h-4" /></button>
                  )}
                  {(p.status === 'completed' || p.status === 'failed') && (
                    <Link to={`/pipelines/${p.id}/results`} className="btn-ghost !py-2 !px-3 text-xs">Resultados</Link>
                  )}
                  <button title="Eliminar" aria-label="Eliminar"
                    onClick={() => { if (window.confirm(`¿Eliminar "${p.name}"? Esto detiene la ejecución y la quita de la lista.`)) remove.mutate(p.id); }}
                    className="btn-ghost !p-2 hover:!text-cyber-red"><Trash2 className="w-4 h-4" /></button>
                </div>
              </div>
              <div className="mt-3"><ProgressBar progress={p.progress} color={STATUS_BADGE[p.status].bar} height={5} /></div>
            </div>
          ))}
          {!isLoading && !error && shown.length === 0 && (
            <div className="text-center py-16 text-gray-600">
              {pipelines?.length ? 'Ninguna investigación coincide con el filtro.' : (
                <>Aún no hay investigaciones. <Link to="/" className="text-cyber-blue hover:underline">Lanza la primera</Link>.</>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

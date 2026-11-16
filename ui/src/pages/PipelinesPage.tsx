import { useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { LayoutGrid, Pause, Play, Table2, Trash2 } from 'lucide-react';
import { Badge } from '@/components/common/Badge';
import { ProgressBar } from '@/components/common/ProgressBar';
import { ErrorBox, Spinner } from '@/components/common/Spinner';
import { useAgents, useCosts, useDeletePipeline, usePipelines, useSetPipelineStatus } from '@/hooks/useApi';
import { useConfigStore } from '@/store/config';
import { formatTokens, formatUsd, STATUS_BADGE, timeAgo } from '@/lib/format';
import type { PipelineJob, PipelineStatus } from '@/types/api';

const FILTERS: { key: 'all' | PipelineStatus; label: string }[] = [
  { key: 'all', label: 'Todas' },
  { key: 'active', label: 'En curso' },
  { key: 'paused', label: 'Pausadas' },
  { key: 'completed', label: 'Completadas' },
  { key: 'failed', label: 'Fallidas' },
];

const SORTS = [
  { key: 'recent', label: 'Más recientes' },
  { key: 'oldest', label: 'Más antiguas' },
  { key: 'cost', label: 'Mayor coste' },
  { key: 'name', label: 'Nombre (A-Z)' },
] as const;

const AGENT_DOT: Record<string, string> = {
  thinking: 'bg-cyber-purple animate-pulse', executing: 'bg-cyber-green animate-pulse', reviewing: 'bg-cyber-red animate-pulse',
  waiting: 'bg-cyber-yellow', idle: 'bg-gray-600',
};

const SORTERS: Record<(typeof SORTS)[number]['key'], (a: PipelineJob, b: PipelineJob) => number> = {
  recent: (a, b) => b.createdAt.localeCompare(a.createdAt),
  oldest: (a, b) => a.createdAt.localeCompare(b.createdAt),
  cost: (a, b) => b.spentUsd - a.spentUsd,
  name: (a, b) => a.name.localeCompare(b.name),
};

const dateTime = (iso: string) => new Date(iso).toLocaleString('es-ES', { dateStyle: 'medium', timeStyle: 'short' });

export function PipelinesPage() {
  const navigate = useNavigate();
  const { data: pipelines, isLoading, error, refetch } = usePipelines();
  const { data: agents } = useAgents();
  const { data: cost } = useCosts();
  const setStatus = useSetPipelineStatus();
  const remove = useDeletePipeline();
  const { listView, listSort, setPrefs } = useConfigStore();
  const [filter, setFilter] = useState<'all' | PipelineStatus>('all');
  const [query, setQuery] = useState('');

  const counts = useMemo(() => {
    const c: Record<string, number> = { all: pipelines?.length ?? 0 };
    pipelines?.forEach((p) => (c[p.status] = (c[p.status] ?? 0) + 1));
    return c;
  }, [pipelines]);

  const shown = useMemo(
    () =>
      (pipelines ?? [])
        .filter((p) => (filter === 'all' || p.status === filter) && p.name.toLowerCase().includes(query.toLowerCase()))
        .sort(SORTERS[listSort]),
    [pipelines, filter, query, listSort],
  );

  const confirmDelete = (p: PipelineJob) => {
    if (window.confirm(`¿Eliminar "${p.name}"? Se borrarán también sus resultados y ficheros. Esta acción no se puede deshacer.`)) {
      remove.mutate(p.id);
    }
  };

  const Actions = ({ p }: { p: PipelineJob }) => (
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
      <button title="Eliminar" aria-label="Eliminar" onClick={() => confirmDelete(p)} className="btn-ghost !p-2 hover:!text-cyber-red"><Trash2 className="w-4 h-4" /></button>
    </div>
  );

  return (
    <div className="page-scroll">
      <div className="max-w-6xl mx-auto px-6 py-8 space-y-6">
        <div className="flex items-end justify-between gap-4 flex-wrap">
          <div>
            <h1 className="text-2xl font-bold text-gray-100">Investigaciones</h1>
            <p className="text-sm text-gray-500">Historial de todas las ejecuciones del enjambre. Se conservan al reiniciar el servidor.</p>
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
          <div className="flex gap-1.5 flex-wrap">
            {FILTERS.map((f) => (
              <button key={f.key} onClick={() => setFilter(f.key)}
                className={`px-3 py-1.5 text-xs rounded-lg border transition-all font-medium ${
                  filter === f.key ? 'bg-dark-hover text-cyber-blue border-cyber-blue/40' : 'text-gray-500 border-dark-primary/40 hover:text-gray-300'
                }`}>
                {f.label} <span className="text-gray-600">{counts[f.key] ?? 0}</span>
              </button>
            ))}
          </div>
          <div className="flex items-center gap-2 ml-auto">
            <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Buscar…" aria-label="Buscar investigaciones"
              className="form-field-input !w-44" />
            <select aria-label="Ordenar por" value={listSort} onChange={(e) => setPrefs({ listSort: e.target.value as typeof listSort })}
              className="form-field-select !w-40">
              {SORTS.map((s) => <option key={s.key} value={s.key}>{s.label}</option>)}
            </select>
            <div className="flex rounded-lg border border-dark-primary/40 overflow-hidden">
              {([['cards', LayoutGrid, 'Tarjetas'], ['table', Table2, 'Tabla']] as const).map(([key, Icon, label]) => (
                <button key={key} onClick={() => setPrefs({ listView: key })} aria-label={`Vista de ${label.toLowerCase()}`} title={label}
                  className={`p-2.5 transition-colors ${listView === key ? 'bg-dark-hover text-cyber-blue' : 'text-gray-500 hover:text-gray-300'}`}>
                  <Icon className="w-4 h-4" />
                </button>
              ))}
            </div>
          </div>
        </div>

        {isLoading && <Spinner label="Cargando investigaciones…" />}
        {error && <ErrorBox message={(error as Error).message} onRetry={() => refetch()} />}

        {listView === 'cards' ? (
          <div className="space-y-3">
            {shown.map((p) => (
              <div key={p.id} onClick={() => navigate(`/pipelines/${p.id}`)} className={`pipeline-card ${p.status} !p-5`}>
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <div className="flex items-center gap-3 mb-1">
                      <span className="font-semibold text-gray-100 truncate">{p.name}</span>
                      <Badge label={STATUS_BADGE[p.status].label} variant={STATUS_BADGE[p.status].variant} dot />
                    </div>
                    <div className="text-[11px] text-gray-500" title={dateTime(p.createdAt)}>
                      {p.type} · {p.domain.toUpperCase()} · {timeAgo(p.createdAt)} · {p.elapsedTime} · {p.tokensUsed} tok · {formatUsd(p.spentUsd)}
                    </div>
                    {p.error && p.status === 'failed' && <div className="text-[11px] text-cyber-red mt-1 line-clamp-2">{p.error}</div>}
                  </div>
                  <Actions p={p} />
                </div>
                <div className="mt-3"><ProgressBar progress={p.progress} color={STATUS_BADGE[p.status].bar} height={5} /></div>
              </div>
            ))}
          </div>
        ) : (
          shown.length > 0 && (
            <div className="glass-panel overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-[10px] text-gray-500 uppercase tracking-wider border-b border-dark-primary/40">
                    <th className="py-3 px-4">Investigación</th><th className="px-2">Estado</th><th className="px-2">Creada</th>
                    <th className="px-2">Duración</th><th className="px-2 text-right">Tokens</th><th className="px-2 text-right">Coste</th>
                    <th className="px-2 w-36">Progreso</th><th className="px-4" />
                  </tr>
                </thead>
                <tbody>
                  {shown.map((p) => (
                    <tr key={p.id} onClick={() => navigate(`/pipelines/${p.id}`)} className="border-t border-dark-primary/40 hover:bg-white/[0.03] cursor-pointer">
                      <td className="py-3 px-4 max-w-xs">
                        <div className="font-medium text-gray-100 truncate">{p.name}</div>
                        <div className="text-[10px] text-gray-600">{p.type} · {p.domain.toUpperCase()}</div>
                      </td>
                      <td className="px-2"><Badge label={STATUS_BADGE[p.status].label} variant={STATUS_BADGE[p.status].variant} dot /></td>
                      <td className="px-2 text-[12px] text-gray-400 whitespace-nowrap">{dateTime(p.createdAt)}</td>
                      <td className="px-2 terminal-font text-[12px] text-gray-400">{p.elapsedTime}</td>
                      <td className="px-2 terminal-font text-[12px] text-gray-400 text-right">{p.tokensUsed}</td>
                      <td className="px-2 terminal-font text-[12px] text-gray-400 text-right">{formatUsd(p.spentUsd)}</td>
                      <td className="px-2"><ProgressBar progress={p.progress} color={STATUS_BADGE[p.status].bar} height={4} /></td>
                      <td className="px-4"><Actions p={p} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        )}

        {!isLoading && !error && shown.length === 0 && (
          <div className="text-center py-16 text-gray-600">
            {pipelines?.length ? 'Ninguna investigación coincide con el filtro.' : (
              <>Aún no hay investigaciones. <Link to="/" className="text-cyber-blue hover:underline">Lanza la primera</Link>.</>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

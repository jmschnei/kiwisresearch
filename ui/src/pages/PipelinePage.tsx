import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { FileText, Pause, Play, Square, Trash2 } from 'lucide-react';
import { Badge } from '@/components/common/Badge';
import { ProgressBar } from '@/components/common/ProgressBar';
import { ErrorBox, Spinner } from '@/components/common/Spinner';
import { AgentGraph } from '@/components/pipeline-graph/AgentGraph';
import { AgentTerminal } from '@/components/terminal/AgentTerminal';
import { StepInspector } from '@/components/inspector/StepInspector';
import { PipelineList } from '@/components/sidebar/PipelineList';
import {
  useCostBreakdown, useDeletePipeline, usePipeline, usePipelines, usePipelineSteps, useReexecuteStep, useSetPipelineStatus,
} from '@/hooks/useApi';
import { toTerminalLog } from '@/hooks/useLiveSync';
import { pipelineApi, ApiError } from '@/services/api';
import { useDashboardStore } from '@/store/dashboard';
import { agentsFromSteps } from '@/lib/agents';
import { formatUsd, STATUS_BADGE } from '@/lib/format';
import type { AgentNode } from '@/types/api';

const EMPTY: never[] = [];

export function PipelinePage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const pipeline = usePipeline(id);
  const { data: all } = usePipelines();
  const { data: steps } = usePipelineSteps(id);
  const { data: breakdown } = useCostBreakdown(id);
  const setStatus = useSetPipelineStatus();
  const remove = useDeletePipeline();
  const reexecute = useReexecuteStep();

  const logs = useDashboardStore((s) => (id ? s.logs[id] : undefined)) ?? EMPTY;
  const setLogs = useDashboardStore((s) => s.setLogs);
  const clearLogs = useDashboardStore((s) => s.clearLogs);
  const terminalTab = useDashboardStore((s) => s.terminalTab);
  const setTerminalTab = useDashboardStore((s) => s.setTerminalTab);
  const inspectorTab = useDashboardStore((s) => s.inspectorTab);
  const setInspectorTab = useDashboardStore((s) => s.setInspectorTab);
  const expandedSteps = useDashboardStore((s) => s.expandedSteps);
  const toggleStep = useDashboardStore((s) => s.toggleStep);
  const [hovered, setHovered] = useState<AgentNode | null>(null);

  // Load the log history once per pipeline; new entries arrive through the WebSocket.
  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    pipelineApi.logs(id).then((raw) => { if (!cancelled) setLogs(id, raw.map(toTerminalLog)); }).catch(() => {});
    return () => { cancelled = true; };
  }, [id, setLogs]);

  const job = pipeline.data;
  const stepKey = steps?.map((s) => s.status).join(',');
  const agents = useMemo(() => agentsFromSteps(steps, job?.status, job?.revising), [stepKey, job?.status, job?.revising]); // eslint-disable-line react-hooks/exhaustive-deps

  if (pipeline.isLoading) return <Spinner label="Cargando investigación…" />;
  if (pipeline.error || !job) {
    const notFound = pipeline.error instanceof ApiError && pipeline.error.status === 404;
    return (
      <div className="max-w-xl mx-auto mt-16 px-6 space-y-4">
        <ErrorBox message={notFound ? 'Esta investigación no existe (¿se reinició el servidor?).' : (pipeline.error as Error)?.message ?? 'Error'} onRetry={notFound ? undefined : () => pipeline.refetch()} />
        <Link to="/pipelines" className="btn-ghost inline-block">← Volver a las investigaciones</Link>
      </div>
    );
  }

  const running = job.status === 'active' || job.status === 'paused';
  const badge = STATUS_BADGE[job.status];
  const hoveredCost = hovered ? breakdown?.[hovered.id] : undefined;

  const onDelete = () => {
    if (window.confirm(`¿Eliminar "${job.name}"? Se detiene la ejecución y se borran sus resultados y ficheros. No se puede deshacer.`)) {
      remove.mutate(job.id, { onSuccess: () => navigate('/pipelines') });
    }
  };
  const onStop = () => {
    if (window.confirm('¿Detener esta investigación? No se puede reanudar (sí puedes re-ejecutar pasos después).')) {
      setStatus.mutate({ id: job.id, status: 'failed', reason: 'Stopped by user' });
    }
  };

  return (
    <div className="flex h-full overflow-hidden">
      <aside className="hidden lg:flex w-[260px] shrink-0 bg-dark-secondary border-r border-dark-primary/40 flex-col">
        <div className="px-5 py-3.5 border-b border-dark-primary/40 text-[11px] font-semibold text-gray-400 uppercase tracking-[1.5px]">
          📋 Investigaciones
        </div>
        <PipelineList pipelines={all ?? []} activeId={job.id} onSelect={(pid) => navigate(`/pipelines/${pid}`)} />
      </aside>

      <section className="flex-1 min-w-0 flex flex-col overflow-hidden">
        <div className="shrink-0 bg-dark-secondary/60 border-b border-dark-primary/40 px-5 py-3">
          <div className="flex items-center gap-3 flex-wrap">
            <h1 className="text-base font-bold text-gray-100 truncate max-w-[50%]" title={job.name}>{job.name}</h1>
            <Badge label={badge.label} variant={badge.variant} dot />
            {job.status === 'active' && !!job.reviewRound && (
              <Badge label={job.revising ? `Reescribiendo · ronda ${job.reviewRound}/${job.reviewMax}` : `Revisión ${job.reviewRound}/${job.reviewMax}`}
                variant={job.revising ? 'pink' : 'red'} dot />
            )}
            <span className="text-[11px] text-gray-500 terminal-font">{job.elapsedTime} · {job.tokensUsed} tok · {formatUsd(job.spentUsd)}</span>
            <div className="ml-auto flex items-center gap-2">
              {job.status === 'active' && (
                <button onClick={() => setStatus.mutate({ id: job.id, status: 'paused' })} className="btn-ghost !py-1.5 !px-3 text-xs flex items-center gap-1.5"><Pause className="w-3.5 h-3.5" /> Pausar</button>
              )}
              {job.status === 'paused' && (
                <button onClick={() => setStatus.mutate({ id: job.id, status: 'active' })} className="btn-ghost !py-1.5 !px-3 text-xs flex items-center gap-1.5"><Play className="w-3.5 h-3.5" /> Reanudar</button>
              )}
              {running && (
                <button onClick={onStop} className="btn-ghost !py-1.5 !px-3 text-xs flex items-center gap-1.5 hover:!text-cyber-red"><Square className="w-3.5 h-3.5" /> Detener</button>
              )}
              {!running && (
                <Link to={`/pipelines/${job.id}/results`} className="btn-primary !py-1.5 !px-4 text-xs flex items-center gap-1.5"><FileText className="w-3.5 h-3.5" /> Ver resultados</Link>
              )}
              <button onClick={onDelete} aria-label="Eliminar" title="Eliminar" className="btn-ghost !p-2 hover:!text-cyber-red"><Trash2 className="w-4 h-4" /></button>
            </div>
          </div>
          <div className="mt-2"><ProgressBar progress={job.progress} color={badge.bar} height={5} /></div>
          {job.status === 'failed' && job.error && <div className="mt-2 text-[11px] text-cyber-red">⚠️ {job.error}</div>}
          {job.status === 'paused' && <div className="mt-2 text-[11px] text-cyber-yellow">⏸ En pausa: el paso en curso termina y después se detiene.</div>}
        </div>

        <div className="flex-1 relative overflow-hidden min-h-[240px]">
          <AgentGraph agents={agents} hoveredAgent={hovered} onHover={setHovered} />
          <div className="absolute top-4 left-4 glass-panel px-4 py-2.5 pointer-events-none max-w-[60%]">
            <div className="text-sm font-bold text-gray-100">🔬 Enjambre multiagente</div>
            <div className="text-[11px] text-gray-500 mt-0.5 truncate">{job.description}</div>
          </div>
          {hovered && (
            <div className="absolute bottom-4 left-4 glass-panel px-4 py-3 pointer-events-none text-xs space-y-1">
              <div className="font-semibold text-gray-100">{hovered.icon} {hovered.name}</div>
              <div className="text-gray-500">Estado: {hovered.status}</div>
              {hoveredCost && <div className="text-gray-400 terminal-font">{hoveredCost.tokens.toLocaleString()} tok · {formatUsd(hoveredCost.costUsd)}</div>}
            </div>
          )}
        </div>

        <div className="h-[200px] shrink-0">
          <AgentTerminal logs={logs} activeTab={terminalTab} onTabChange={setTerminalTab} onClear={() => clearLogs(job.id)} />
        </div>
      </section>

      <aside className="hidden md:flex w-[340px] shrink-0 bg-dark-secondary border-l border-dark-primary/40 flex-col">
        <div className="px-5 py-3.5 border-b border-dark-primary/40 flex items-center justify-between">
          <span className="text-sm font-semibold text-gray-200">🔍 Inspector de pasos</span>
          <span className="text-[10px] text-gray-500 terminal-font">
            {steps?.filter((s) => s.status === 'done').length ?? 0} / {steps?.length ?? 0}
          </span>
        </div>
        <StepInspector
          steps={steps ?? []}
          activeTab={inspectorTab}
          onTabChange={setInspectorTab}
          onToggleStep={toggleStep}
          expandedSteps={expandedSteps}
          onReexecute={running ? undefined : (n, cascade) => reexecute.mutate({ id: job.id, step: n, cascade })}
        />
      </aside>
    </div>
  );
}

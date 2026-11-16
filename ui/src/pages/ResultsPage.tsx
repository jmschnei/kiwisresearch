import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { Download } from 'lucide-react';
import { Badge } from '@/components/common/Badge';
import { ErrorBox, Spinner } from '@/components/common/Spinner';
import { useArtifacts, usePaper, usePipeline, useReview } from '@/hooks/useApi';
import { API_ORIGIN, ApiError, resultsApi } from '@/services/api';
import { CONSENSUS_LABEL, formatUsd } from '@/lib/format';

type Tab = 'summary' | 'research' | 'review' | 'artifacts';
const TABS: { key: Tab; label: string }[] = [
  { key: 'summary', label: '📄 Artículo' },
  { key: 'research', label: '🔬 Investigación' },
  { key: 'review', label: '🏆 Revisión' },
  { key: 'artifacts', label: '📦 Artefactos' },
];
const TEXT_TYPES = ['json', 'py', 'tex', 'md', 'csv'];

/** The full pipeline state, saved by the backend as `state.json`. */
function useResearchState(id: string | undefined, enabled: boolean) {
  return useQuery({
    queryKey: ['research-state', id],
    enabled: !!id && enabled,
    retry: false,
    queryFn: async () => JSON.parse(await resultsApi.artifactText(id!, 'state.json')) as Record<string, any>,
  });
}

const Section = ({ title, children }: { title: string; children: React.ReactNode }) => (
  <div className="glass-panel p-5">
    <div className="text-[11px] text-cyber-cyan uppercase tracking-wider font-semibold mb-3">{title}</div>
    {children}
  </div>
);

const Pre = ({ children }: { children: React.ReactNode }) => (
  <pre className="terminal-font text-[11px] bg-dark-primary/60 rounded-lg p-3 text-gray-300 overflow-x-auto whitespace-pre-wrap border border-dark-primary/40 max-h-80">{children}</pre>
);

const pretty = (v: unknown) => (typeof v === 'string' ? v : JSON.stringify(v, null, 2));
const isEmpty = (v: unknown) => v == null || v === '' || (typeof v === 'object' && Object.keys(v as object).length === 0);

export function ResultsPage() {
  const { id } = useParams<{ id: string }>();
  const [tab, setTab] = useState<Tab>('summary');
  const [preview, setPreview] = useState<{ name: string; text: string } | null>(null);
  const job = usePipeline(id);
  const paper = usePaper(id);
  const review = useReview(id);
  const artifacts = useArtifacts(id);
  const state = useResearchState(id, !!job.data && job.data.status !== 'active');

  if (job.isLoading) return <Spinner label="Cargando…" />;
  if (job.error || !job.data) {
    return (
      <div className="max-w-xl mx-auto mt-16 px-6 space-y-4">
        <ErrorBox message="Esta investigación no existe (¿se reinició el servidor?)." />
        <Link to="/pipelines" className="btn-ghost inline-block">← Volver</Link>
      </div>
    );
  }

  const j = job.data;
  const st = state.data ?? {};
  const p = paper.data;
  const notReady = paper.error instanceof ApiError && paper.error.code === 'NOT_READY';
  const consensus = p ? CONSENSUS_LABEL[p.reviewConsensus] : null;
  const lastReview = (st.review_feedback as any[] | undefined)?.slice(-1)[0];
  const chartData = (review.data?.metrics ?? []).map((m) => ({ name: m.name, score: m.score, color: m.color, description: m.description }));

  const openPreview = async (name: string) => {
    try {
      setPreview({ name, text: await resultsApi.artifactText(j.id, name) });
    } catch {
      setPreview({ name, text: 'No se pudo cargar el artefacto.' });
    }
  };

  return (
    <div className="page-scroll">
      <div className="max-w-5xl mx-auto px-6 py-8 space-y-6">
        <div>
          <Link to={`/pipelines/${j.id}`} className="text-xs text-cyber-blue hover:underline">← Volver al monitor</Link>
          <div className="flex items-start justify-between gap-4 mt-2 flex-wrap">
            <div>
              <h1 className="text-2xl font-bold text-gray-100">{p?.title && p.title !== 'Untitled' ? p.title : j.name}</h1>
              <div className="text-xs text-gray-500 mt-1">
                {j.name} · {j.elapsedTime} · {j.tokensUsed} tok · {formatUsd(j.spentUsd)} (estimado)
              </div>
            </div>
            {consensus && <Badge label={consensus.label} variant={consensus.variant} size="md" dot />}
          </div>
          {j.status === 'active' && <div className="mt-3 text-sm text-cyber-yellow">⏳ La investigación sigue en curso; los resultados aparecerán al terminar.</div>}
          {j.status === 'failed' && j.error && <div className="mt-3 text-sm text-cyber-red">⚠️ {j.error}</div>}
        </div>

        <div className="flex gap-1 border-b border-dark-primary/40">
          {TABS.map((t) => (
            <button key={t.key} onClick={() => setTab(t.key)}
              className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${tab === t.key ? 'text-cyber-blue border-cyber-blue' : 'text-gray-500 border-transparent hover:text-gray-300'}`}>
              {t.label}
            </button>
          ))}
        </div>

        {tab === 'summary' && (
          <div className="space-y-4">
            {paper.isLoading && <Spinner label="Cargando artículo…" />}
            {notReady && <ErrorBox message="El artículo todavía no se ha escrito." />}
            {paper.error && !notReady && <ErrorBox message={(paper.error as Error).message} />}
            {p && (
              <>
                <Section title="Resumen (abstract)">
                  <p className="text-sm text-gray-300 leading-relaxed whitespace-pre-wrap">{p.abstract || 'El agente redactor no generó un resumen.'}</p>
                  <div className="text-[11px] text-gray-500 mt-3">Autores: {p.authors.join(', ')}</div>
                </Section>
                <Section title="Documento">
                  {p.pdfUrl ? (
                    <>
                      <iframe title="Paper PDF" src={`${API_ORIGIN}${p.pdfUrl}`} className="w-full h-[640px] rounded-lg border border-dark-primary/40 bg-white" />
                      <a href={`${API_ORIGIN}${p.pdfUrl}`} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 mt-3 text-xs text-cyber-blue hover:underline">
                        <Download className="w-3.5 h-3.5" /> Abrir PDF en una pestaña
                      </a>
                    </>
                  ) : (
                    <div className="text-sm text-gray-400">
                      No se generó el PDF (requiere <code className="terminal-font">pdflatex</code> instalado en el servidor). Puedes descargar el código LaTeX
                      desde la pestaña de artefactos.
                    </div>
                  )}
                </Section>
              </>
            )}
          </div>
        )}

        {tab === 'research' && (
          <div className="space-y-4">
            {state.isLoading && <Spinner label="Cargando estado de la investigación…" />}
            {state.error && <ErrorBox message="El estado de la investigación aún no está disponible." />}
            {!state.isLoading && !state.error && (
              <>
                <Section title="Hipótesis"><p className="text-sm text-gray-300">{st.hypothesis || '—'}</p></Section>
                <Section title="Revisión de literatura">
                  {isEmpty(st.literature_review) ? <p className="text-sm text-gray-500">Sin datos de literatura.</p> : (
                    <div className="space-y-3 text-sm text-gray-300">
                      {st.literature_review.summary && <p className="whitespace-pre-wrap">{st.literature_review.summary}</p>}
                      {st.literature_review.gaps?.length > 0 && (
                        <ul className="list-disc pl-5 text-gray-400">{st.literature_review.gaps.map((g: unknown, i: number) => <li key={i}>{pretty(g)}</li>)}</ul>
                      )}
                    </div>
                  )}
                </Section>
                <Section title="Diseño experimental">{isEmpty(st.experiment_plan) ? <p className="text-sm text-gray-500">Sin plan experimental.</p> : <Pre>{pretty(st.experiment_plan)}</Pre>}</Section>
                <Section title="Ejecución">
                  {isEmpty(st.execution_results) ? <p className="text-sm text-gray-500">No se ejecutó código.</p> : <Pre>{pretty(st.execution_results)}</Pre>}
                </Section>
                <Section title="Análisis">{isEmpty(st.analysis) ? <p className="text-sm text-gray-500">Sin análisis.</p> : <Pre>{pretty(st.analysis)}</Pre>}</Section>
              </>
            )}
          </div>
        )}

        {tab === 'review' && (
          <div className="space-y-4">
            {review.isLoading && <Spinner label="Cargando revisión…" />}
            {review.data && review.data.metrics.length === 0 && <ErrorBox message="Todavía no hay revisión por pares para esta investigación." />}
            {chartData.length > 0 && (
              <Section title="Puntuación por criterio (10 − penalizaciones por severidad)">
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={chartData} layout="vertical" margin={{ left: 30, right: 20 }}>
                      <CartesianGrid stroke="#1e2940" horizontal={false} />
                      <XAxis type="number" domain={[0, 10]} stroke="#6b7280" fontSize={11} />
                      <YAxis type="category" dataKey="name" stroke="#9ca3af" fontSize={12} width={110} />
                      <Tooltip cursor={{ fill: 'rgba(255,255,255,0.04)' }} contentStyle={{ background: '#111827', border: '1px solid #1e2940', borderRadius: 8, fontSize: 12 }} />
                      <Bar dataKey="score" radius={[0, 6, 6, 0]}>
                        {chartData.map((d) => <Cell key={d.name} fill={d.color} />)}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </Section>
            )}
            {chartData.map((m) => (
              <div key={m.name} className="metric-card">
                <div className="flex items-center justify-between"><span className="text-sm font-semibold text-gray-200">{m.name}</span><span className="terminal-font text-sm" style={{ color: m.color }}>{m.score}/10</span></div>
                <p className="text-[12px] text-gray-500 mt-1">{m.description}</p>
              </div>
            ))}
            {lastReview && (
              <Section title="Informe completo del revisor">
                {lastReview.decision_rationale && <p className="text-sm text-gray-300 mb-3">{lastReview.decision_rationale}</p>}
                <Pre>{pretty(lastReview)}</Pre>
              </Section>
            )}
          </div>
        )}

        {tab === 'artifacts' && (
          <div className="space-y-4">
            {artifacts.isLoading && <Spinner />}
            {artifacts.data?.length === 0 && <p className="text-sm text-gray-500">No hay artefactos.</p>}
            <div className="space-y-2">
              {artifacts.data?.map((a) => (
                <div key={a.id} className="metric-card !p-3 flex items-center gap-3">
                  <span className="terminal-font text-[10px] uppercase px-2 py-0.5 rounded bg-dark-hover text-gray-400 w-12 text-center">{a.type}</span>
                  <span className="flex-1 text-sm text-gray-200 truncate">{a.name}</span>
                  <span className="text-[11px] text-gray-600">{a.size}</span>
                  {TEXT_TYPES.includes(a.type) && <button onClick={() => openPreview(a.id)} className="text-xs text-cyber-blue hover:underline">Ver</button>}
                  <a href={resultsApi.artifactUrl(j.id, a.id)} download className="text-xs text-cyber-blue hover:underline flex items-center gap-1"><Download className="w-3.5 h-3.5" /> Descargar</a>
                </div>
              ))}
            </div>
            {preview && (
              <Section title={`Vista previa — ${preview.name}`}>
                <Pre>{preview.text.length > 20000 ? `${preview.text.slice(0, 20000)}\n… (truncado)` : preview.text}</Pre>
              </Section>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

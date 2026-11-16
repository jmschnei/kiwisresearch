import React, { useEffect, useMemo, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { ChevronDown, ChevronUp, Rocket } from 'lucide-react';
import { Badge } from '@/components/common/Badge';
import { ProgressBar } from '@/components/common/ProgressBar';
import { useBackendConfig, useBackendHealth, useCreateResearch, usePipelines } from '@/hooks/useApi';
import { useConfigStore } from '@/store/config';
import { depthOptions, RESEARCH_DOMAINS, RESEARCH_TYPES, STATUS_BADGE, timeAgo } from '@/lib/format';
import type { CreateResearchRequest } from '@/types/api';

const EXAMPLES = [
  'Improving graph neural networks for molecular property prediction',
  'Federated learning for medical imaging with non-IID data',
  'Transformer architectures for time series forecasting',
  'Efficient neural architecture search for edge devices',
];

const PIPELINE_STEPS = [
  ['🧠', 'Hipótesis'], ['📚', 'Literatura'], ['💻', 'Diseño'], ['⚙️', 'Ejecución'],
  ['📊', 'Análisis'], ['📝', 'Redacción'], ['🔍', 'Revisión'],
];

export function HomePage() {
  const navigate = useNavigate();
  const location = useLocation();
  const prefs = useConfigStore();
  const create = useCreateResearch();
  const { data: pipelines } = usePipelines();
  const health = useBackendHealth();
  const { data: config } = useBackendConfig();

  const [topic, setTopic] = useState('');
  const [hypothesis, setHypothesis] = useState('');
  const [type, setType] = useState('paper');
  const [domain, setDomain] = useState('ml');
  const [model, setModel] = useState(prefs.defaultModel);
  const [depth, setDepth] = useState(prefs.defaultDepth);
  const [budget, setBudget] = useState(prefs.defaultBudgetUsd);
  const [maxTokens, setMaxTokens] = useState<number | ''>('');
  const [showAdvanced, setShowAdvanced] = useState(false);

  // The library page can send a topic here
  useEffect(() => {
    const t = (location.state as { topic?: string } | null)?.topic;
    if (t) setTopic(t);
  }, [location.state]);

  const backendDown = health.isError;
  const models = useMemo(
    () => (config ? [...new Set(Object.values(config.providers).filter((p) => p.available).flatMap((p) => p.models))] : []),
    [config],
  );
  const placeholderAgents = useMemo(
    () => (config ? Object.entries(config.agents).filter(([, a]) => !config.providers[a.provider]?.available).map(([r]) => r) : []),
    [config],
  );

  const canSubmit = topic.trim().length > 0 && !backendDown && !create.isPending;

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmit) return;
    const body: CreateResearchRequest = {
      title: topic.trim(),
      type: type as CreateResearchRequest['type'],
      domain: domain as CreateResearchRequest['domain'],
      hypothesis: hypothesis.trim(),
      depthLevel: depth,
      budgetUsd: budget || 0,
      ...(model ? { model } : {}),
      ...(maxTokens ? { maxTokensPerIteration: Number(maxTokens) } : {}),
    };
    create.mutate(body, { onSuccess: (r) => navigate(`/pipelines/${r.pipelineId}`) });
  };

  const recent = (pipelines ?? []).slice(0, 4);

  return (
    <div className="page-scroll">
      <div className="max-w-4xl mx-auto px-6 py-12">
        <div className="text-center mb-8">
          <h1 className="text-4xl font-extrabold gradient-hero mb-3">¿Qué quieres investigar?</h1>
          <p className="text-gray-400 max-w-2xl mx-auto">
            Describe un tema o una pregunta. Un enjambre de agentes formulará hipótesis, revisará la literatura, diseñará y ejecutará
            experimentos, escribirá el artículo y lo someterá a una revisión adversarial.
          </p>
        </div>

        <div className="flex items-center justify-center flex-wrap gap-x-2 gap-y-1 mb-8 text-[11px] text-gray-500">
          {PIPELINE_STEPS.map(([icon, label], i) => (
            <React.Fragment key={label}>
              <span className="px-2.5 py-1 rounded-full bg-dark-tertiary border border-dark-primary/40">{icon} {label}</span>
              {i < PIPELINE_STEPS.length - 1 && <span className="text-gray-700">→</span>}
            </React.Fragment>
          ))}
        </div>

        {backendDown && (
          <div className="glass-panel border-cyber-red/30 p-4 mb-5 text-sm text-gray-300">
            ⚠️ No se puede conectar con el backend. Arráncalo con <code className="terminal-font text-cyber-cyan">kiwis serve</code> (requiere{' '}
            <code className="terminal-font text-cyber-cyan">pip install -e ".[api]"</code>).
          </div>
        )}
        {!backendDown && placeholderAgents.length > 0 && (
          <div className="glass-panel border-cyber-yellow/30 p-4 mb-5 text-sm text-gray-300">
            ⚠️ {placeholderAgents.length} de {Object.keys(config!.agents).length} agentes no tienen proveedor LLM disponible (falta la API key) y
            generarán contenido de ejemplo vacío.{' '}
            <Link to="/settings" className="text-cyber-blue hover:underline">Ver ajustes</Link>
          </div>
        )}

        <form onSubmit={submit} className="glass-panel p-6 space-y-4">
          <div>
            <label htmlFor="topic" className="block text-[11px] text-cyber-cyan uppercase tracking-wider font-semibold mb-2">
              Tema o pregunta de investigación
            </label>
            <textarea
              id="topic" rows={3} autoFocus value={topic} onChange={(e) => setTopic(e.target.value)}
              className="form-field-input resize-none text-base"
              placeholder="Ej.: Mejorar las redes neuronales de grafos para la predicción de propiedades moleculares"
            />
            <div className="flex flex-wrap gap-2 mt-2">
              {EXAMPLES.map((ex) => (
                <button key={ex} type="button" onClick={() => setTopic(ex)}
                  className="text-[11px] px-2.5 py-1 rounded-full border border-dark-primary/40 text-gray-500 hover:text-cyber-blue hover:border-cyber-blue/40 transition-colors">
                  {ex}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label htmlFor="hyp" className="block text-[11px] text-cyber-cyan uppercase tracking-wider font-semibold mb-2">
              Hipótesis inicial <span className="text-gray-600 normal-case tracking-normal">(opcional — si la das, se omite la generación de hipótesis)</span>
            </label>
            <textarea id="hyp" rows={2} value={hypothesis} onChange={(e) => setHypothesis(e.target.value)}
              className="form-field-input resize-none" placeholder="Ej.: Un mecanismo de atención sobre aristas mejora el MAE en un 5 %" />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <select aria-label="Tipo de investigación" className="form-field-select" value={type} onChange={(e) => setType(e.target.value)}>
              {RESEARCH_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
            </select>
            <select aria-label="Dominio" className="form-field-select" value={domain} onChange={(e) => setDomain(e.target.value)}>
              {RESEARCH_DOMAINS.map((d) => <option key={d} value={d}>{d.toUpperCase()}</option>)}
            </select>
          </div>

          <button type="button" onClick={() => setShowAdvanced((v) => !v)}
            className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-300">
            {showAdvanced ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />} Parámetros avanzados
          </button>

          {showAdvanced && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 animate-fade-in">
              <label className="text-[11px] text-gray-500 space-y-1">
                Modelo (para todos los agentes)
                <select className="form-field-select" value={model} onChange={(e) => setModel(e.target.value)}>
                  <option value="">Automático (el configurado por agente)</option>
                  {models.map((m) => <option key={m} value={m}>{m}</option>)}
                </select>
              </label>
              <label className="text-[11px] text-gray-500 space-y-1">
                Profundidad (rondas de revisión y reescritura)
                <select className="form-field-select" value={depth} onChange={(e) => setDepth(e.target.value as typeof depth)}>
                  {depthOptions(Number(config?.pipeline.peer_review_critique_rounds ?? 2)).map((d) => <option key={d.value} value={d.value}>{d.label}</option>)}
                </select>
              </label>
              <label className="text-[11px] text-gray-500 space-y-1">
                Presupuesto máximo estimado (USD, 0 = sin límite)
                <input type="number" min={0} step={1} className="form-field-input" value={budget}
                  onChange={(e) => setBudget(Number(e.target.value))} />
              </label>
              <label className="text-[11px] text-gray-500 space-y-1">
                Máx. tokens por respuesta (vacío = el configurado)
                <input type="number" min={256} step={1000} className="form-field-input" value={maxTokens}
                  onChange={(e) => setMaxTokens(e.target.value ? Number(e.target.value) : '')} />
              </label>
            </div>
          )}

          <div className="flex items-center justify-end gap-3 pt-2">
            {create.isError && <span className="text-xs text-cyber-red">{(create.error as Error).message}</span>}
            <button type="submit" disabled={!canSubmit} className="btn-primary flex items-center gap-2 disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:translate-y-0">
              <Rocket className="w-4 h-4" /> {create.isPending ? 'Lanzando…' : 'Lanzar investigación'}
            </button>
          </div>
        </form>

        {recent.length > 0 && (
          <div className="mt-10">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-semibold text-gray-300">Investigaciones recientes</h2>
              <Link to="/pipelines" className="text-xs text-cyber-blue hover:underline">Ver todas →</Link>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {recent.map((p) => (
                <Link key={p.id} to={`/pipelines/${p.id}`} className={`pipeline-card block ${p.status}`}>
                  <div className="flex items-center justify-between gap-2 mb-2">
                    <span className="text-sm font-semibold text-gray-200 truncate">{p.name}</span>
                    <Badge label={STATUS_BADGE[p.status].label} variant={STATUS_BADGE[p.status].variant} dot />
                  </div>
                  <ProgressBar progress={p.progress} color={STATUS_BADGE[p.status].bar} height={4} />
                  <div className="mt-2 text-[10px] text-gray-600">{timeAgo(p.createdAt)}</div>
                </Link>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

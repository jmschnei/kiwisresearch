import { Badge } from '@/components/common/Badge';
import { ErrorBox, Spinner } from '@/components/common/Spinner';
import { useBackendConfig, useBackendHealth } from '@/hooks/useApi';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { API_BASE, storageApi } from '@/services/api';
import { useConfigStore } from '@/store/config';
import { useDashboardStore } from '@/store/dashboard';
import { depthOptions } from '@/lib/format';

const Section = ({ title, children }: { title: string; children: React.ReactNode }) => (
  <section className="glass-panel p-5">
    <h2 className="text-[11px] text-cyber-cyan uppercase tracking-wider font-semibold mb-4">{title}</h2>
    {children}
  </section>
);

const Row = ({ label, children }: { label: string; children: React.ReactNode }) => (
  <div className="flex items-center justify-between gap-4 py-1.5 text-sm">
    <span className="text-gray-500">{label}</span>
    <span className="text-gray-200 terminal-font text-right">{children}</span>
  </div>
);

const fmtBytes = (n: number) => (n > 1e9 ? `${(n / 1e9).toFixed(1)} GB` : n > 1e6 ? `${(n / 1e6).toFixed(1)} MB` : `${Math.ceil(n / 1e3)} KB`);

function StorageSection() {
  const qc = useQueryClient();
  const info = useQuery({ queryKey: ['storage'], queryFn: storageApi.info, retry: false });
  const [days, setDays] = useState(30);
  const [keep, setKeep] = useState(20);
  const [mode, setMode] = useState<'age' | 'count'>('age');
  const body = mode === 'age' ? { olderThanDays: days } : { keepLast: keep };
  const preview = useMutation({ mutationFn: () => storageApi.cleanup({ ...body, dryRun: true }) });
  const clean = useMutation({
    mutationFn: () => storageApi.cleanup(body),
    onSuccess: () => {
      preview.reset();
      qc.invalidateQueries({ queryKey: ['storage'] });
      qc.invalidateQueries({ queryKey: ['pipelines'] });
    },
  });
  const r = info.data?.retention;

  return (
    <Section title="Almacenamiento">
      {info.isLoading && <Spinner label="Calculando…" />}
      {info.data && (
        <>
          <Row label="Investigaciones guardadas">{info.data.jobs} ({info.data.finished} terminadas)</Row>
          <Row label="Espacio en disco">{fmtBytes(info.data.totalBytes)}</Row>
          <Row label="Limpieza automática">
            {r?.max_age_days || r?.max_jobs
              ? [r.max_age_days && `> ${r.max_age_days} días`, r.max_jobs && `máx. ${r.max_jobs}`].filter(Boolean).join(' · ')
              : 'desactivada (retention en kiwis_config.yaml)'}
          </Row>
          <div className="flex flex-wrap items-end gap-3 mt-4">
            <label className="text-[11px] text-gray-500 space-y-1">
              Borrar terminadas
              <select className="form-field-select" value={mode} onChange={(e) => { setMode(e.target.value as 'age' | 'count'); preview.reset(); }}>
                <option value="age">más antiguas que…</option>
                <option value="count">salvo las últimas…</option>
              </select>
            </label>
            <label className="text-[11px] text-gray-500 space-y-1">
              {mode === 'age' ? 'Días' : 'Conservar'}
              <input type="number" min={mode === 'age' ? 0 : 0} className="form-field-input w-24"
                value={mode === 'age' ? days : keep}
                onChange={(e) => { (mode === 'age' ? setDays : setKeep)(Number(e.target.value)); preview.reset(); }} />
            </label>
            <button className="px-3 py-2 text-xs rounded-lg border border-dark-primary/60 text-gray-300 hover:bg-dark-hover" onClick={() => preview.mutate()} disabled={preview.isPending}>
              Ver qué se borraría
            </button>
            {preview.data && preview.data.deleted > 0 && (
              <button className="px-3 py-2 text-xs rounded-lg bg-cyber-red/20 text-cyber-red border border-cyber-red/40 hover:bg-cyber-red/30" onClick={() => clean.mutate()} disabled={clean.isPending}>
                Borrar {preview.data.deleted} ({fmtBytes(preview.data.freedBytes)})
              </button>
            )}
          </div>
          {preview.data && (
            <p className="text-[11px] text-gray-500 mt-2">
              {preview.data.deleted === 0 ? 'No hay nada que borrar con ese criterio.' : `Se borrarían: ${preview.data.items.map((i) => i.title).join(', ')}. Las investigaciones en curso o pausadas nunca se borran.`}
            </p>
          )}
          {clean.data && <p className="text-[11px] text-cyber-green mt-2">Borradas {clean.data.deleted} investigaciones; liberados {fmtBytes(clean.data.freedBytes)}.</p>}
          {(preview.error || clean.error) && <p className="text-[11px] text-cyber-red mt-2">{((preview.error || clean.error) as Error).message}</p>}
        </>
      )}
    </Section>
  );
}

export function SettingsPage() {
  const health = useBackendHealth();
  const config = useBackendConfig();
  const wsState = useDashboardStore((s) => s.wsState);
  const prefs = useConfigStore();
  const cfg = config.data;

  return (
    <div className="page-scroll">
      <div className="max-w-4xl mx-auto px-6 py-8 space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-100">Ajustes</h1>
          <p className="text-sm text-gray-500">Estado del backend y preferencias. La configuración de agentes y proveedores se edita en <code className="terminal-font">kiwis_config.yaml</code>.</p>
        </div>

        <Section title="Conexión">
          <Row label="API">{API_BASE}</Row>
          <Row label="Backend">
            {health.data ? <Badge label={`OK · v${health.data.version}`} variant="green" dot /> : health.isError ? <Badge label="Sin conexión" variant="red" dot /> : '…'}
          </Row>
          <Row label="Tiempo real (WebSocket)">
            <Badge label={wsState === 'connected' ? 'Conectado' : wsState === 'reconnecting' ? 'Conectando' : 'Desconectado'}
              variant={wsState === 'connected' ? 'green' : wsState === 'reconnecting' ? 'yellow' : 'red'} dot />
          </Row>
        </Section>

        {config.isLoading && <Spinner label="Cargando configuración del backend…" />}
        {config.error && <ErrorBox message={(config.error as Error).message} onRetry={() => config.refetch()} />}

        {cfg && (
          <>
            <Section title="Proveedores LLM">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {Object.entries(cfg.providers).map(([name, p]) => (
                  <div key={name} className="metric-card">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-sm font-semibold text-gray-200">{p.name}</span>
                      <Badge label={p.available ? 'Disponible' : 'Sin API key'} variant={p.available ? 'green' : 'yellow'} dot />
                    </div>
                    <div className="text-[11px] text-gray-500">Modelo por defecto: <span className="terminal-font text-gray-400">{p.defaultModel}</span></div>
                    {!p.available && p.apiKeyEnvVar && (
                      <div className="text-[11px] text-gray-500 mt-1">Define la variable de entorno <code className="terminal-font text-cyber-cyan">{p.apiKeyEnvVar}</code> y reinicia el servidor.</div>
                    )}
                  </div>
                ))}
              </div>
            </Section>

            <Section title="Agentes">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-[10px] text-gray-500 uppercase tracking-wider">
                      <th className="py-2 pr-4">Agente</th><th className="pr-4">Modelo</th><th className="pr-4">Proveedor</th><th className="pr-4">Temp.</th><th>Máx. tokens</th>
                    </tr>
                  </thead>
                  <tbody className="terminal-font text-[12px] text-gray-300">
                    {Object.entries(cfg.agents).map(([role, a]) => (
                      <tr key={role} className="border-t border-dark-primary/40">
                        <td className="py-2 pr-4 font-sans">{role}</td>
                        <td className="pr-4">{a.model}</td>
                        <td className="pr-4">
                          {a.provider} {cfg.providers[a.provider] && !cfg.providers[a.provider].available && <span className="text-cyber-yellow">⚠</span>}
                        </td>
                        <td className="pr-4">{a.temperature}</td>
                        <td>{a.maxTokens}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Section>

            <Section title="Entorno de ejecución">
              <Row label="Sandbox">{cfg.sandbox.mode}</Row>
              <Row label="Timeout">{cfg.sandbox.timeout_seconds}s</Row>
              {cfg.services?.semanticScholar && (
                <Row label="Semantic Scholar">
                  {cfg.services.semanticScholar.configured
                    ? <Badge label="API key configurada" variant="green" dot />
                    : <Badge label="Sin API key (límite compartido)" variant="yellow" dot />}
                </Row>
              )}
              <Row label="Memoria vectorial">{cfg.memory.enabled ? `${cfg.memory.vector_store} (${cfg.memory.urlConfigured ? 'servidor configurado' : cfg.memory.persist_dir})` : 'desactivada'}</Row>
            </Section>
            {cfg.services?.semanticScholar && !cfg.services.semanticScholar.configured && (
              <p className="text-[11px] text-gray-600 -mt-3 px-1">
                Define <code className="terminal-font text-cyber-cyan">{cfg.services.semanticScholar.envVar}</code> (clave gratuita en semanticscholar.org/product/api) para evitar los errores 429; mientras tanto la bibliografía se obtiene solo de arXiv y de la memoria.
              </p>
            )}
          </>
        )}

        <StorageSection />

        <Section title="Preferencias para nuevas investigaciones">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <label className="text-[11px] text-gray-500 space-y-1">
              Modelo por defecto
              <input className="form-field-input" placeholder="vacío = el de cada agente" value={prefs.defaultModel}
                onChange={(e) => prefs.setPrefs({ defaultModel: e.target.value })} />
            </label>
            <label className="text-[11px] text-gray-500 space-y-1">
              Profundidad
              <select className="form-field-select" value={prefs.defaultDepth}
                onChange={(e) => prefs.setPrefs({ defaultDepth: e.target.value as typeof prefs.defaultDepth })}>
                {depthOptions(Number(cfg?.pipeline.peer_review_critique_rounds ?? 2)).map((d) => <option key={d.value} value={d.value}>{d.label}</option>)}
              </select>
            </label>
            <label className="text-[11px] text-gray-500 space-y-1">
              Presupuesto (USD, 0 = sin límite)
              <input type="number" min={0} className="form-field-input" value={prefs.defaultBudgetUsd}
                onChange={(e) => prefs.setPrefs({ defaultBudgetUsd: Number(e.target.value) })} />
            </label>
          </div>
          <p className="text-[11px] text-gray-600 mt-3">Se guardan en este navegador y se usan como valores iniciales del formulario de inicio.</p>
        </Section>
      </div>
    </div>
  );
}

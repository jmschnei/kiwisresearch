import { Badge } from '@/components/common/Badge';
import { ErrorBox, Spinner } from '@/components/common/Spinner';
import { useBackendConfig, useBackendHealth } from '@/hooks/useApi';
import { API_BASE } from '@/services/api';
import { useConfigStore } from '@/store/config';
import { useDashboardStore } from '@/store/dashboard';
import { DEPTH_LEVELS } from '@/lib/format';

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
              <Row label="Memoria vectorial">{cfg.memory.enabled ? `${cfg.memory.vector_store} (${cfg.memory.persist_dir})` : 'desactivada'}</Row>
            </Section>
          </>
        )}

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
                {DEPTH_LEVELS.map((d) => <option key={d.value} value={d.value}>{d.label}</option>)}
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

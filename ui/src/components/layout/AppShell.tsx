import React from 'react';
import { NavLink, Link, Outlet } from 'react-router-dom';
import { Sparkles } from 'lucide-react';
import { Logo } from '@/components/header/Logo';
import { CostDisplay } from '@/components/header/CostDisplay';
import { SwarmStatus } from '@/components/header/SwarmStatus';
import { Toaster } from '@/components/common/Toaster';
import { useAgents, useCosts } from '@/hooks/useApi';
import { useLiveSync } from '@/hooks/useLiveSync';
import { useDashboardStore } from '@/store/dashboard';
import { formatTokens, formatUsd } from '@/lib/format';

const NAV = [
  { to: '/', label: 'Inicio', end: true },
  { to: '/pipelines', label: 'Investigaciones', end: false },
  { to: '/library', label: 'Biblioteca', end: false },
  { to: '/settings', label: 'Ajustes', end: false },
];

const WS_DOT = {
  connected: { cls: 'bg-cyber-green', label: 'En vivo' },
  reconnecting: { cls: 'bg-cyber-yellow animate-pulse', label: 'Conectando…' },
  disconnected: { cls: 'bg-cyber-red', label: 'Sin conexión' },
} as const;

export const AppShell: React.FC = () => {
  useLiveSync();
  const { data: cost } = useCosts();
  const { data: agents } = useAgents();
  const wsState = useDashboardStore((s) => s.wsState);
  const ws = WS_DOT[wsState];

  return (
    <div className="flex flex-col h-screen w-screen bg-dark-primary text-gray-200 overflow-hidden">
      <header className="h-[64px] shrink-0 bg-dark-secondary border-b border-dark-primary/40 flex items-center gap-6 px-6 relative z-10">
        <Link to="/" aria-label="Inicio">
          <Logo />
        </Link>
        <nav className="flex items-center gap-1 ml-2">
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.end}
              className={({ isActive }) =>
                `px-3.5 py-2 rounded-lg text-sm font-medium transition-colors ${
                  isActive ? 'bg-dark-hover text-cyber-blue' : 'text-gray-400 hover:text-gray-200'
                }`
              }
            >
              {n.label}
            </NavLink>
          ))}
        </nav>

        <div className="ml-auto hidden xl:flex items-center gap-6">
          <div className="hidden 2xl:block">
            <CostDisplay
              tokens={formatTokens(cost?.tokensUsed ?? 0)}
              costUsd={formatUsd(cost?.costUsd ?? 0)}
              uptime={cost?.uptime ?? '00:00:00'}
            />
          </div>
          <SwarmStatus
            active={(agents ?? []).filter((a) => a.status !== 'idle' && a.status !== 'waiting').length}
            total={agents?.length ?? 7}
          />
        </div>
        <div className="ml-auto xl:ml-0 flex items-center gap-2 text-[11px] text-gray-500 whitespace-nowrap" title="Conexión en tiempo real">
          <span className={`w-2 h-2 rounded-full ${ws.cls}`} />
          {ws.label}
        </div>
        <Link to="/" className="btn-primary flex items-center gap-2 !py-2 whitespace-nowrap shrink-0">
          <Sparkles className="w-4 h-4" /> Nueva investigación
        </Link>
      </header>
      <main className="flex-1 min-h-0">
        <Outlet />
      </main>
      <Toaster />
    </div>
  );
};

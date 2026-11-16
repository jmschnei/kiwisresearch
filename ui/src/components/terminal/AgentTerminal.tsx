import React, { useEffect, useRef } from 'react';
import type { TerminalLog, TerminalTab } from '@/types/api';

interface Props {
  logs: TerminalLog[];
  activeTab: TerminalTab;
  onTabChange: (tab: TerminalTab) => void;
  onClear: () => void;
}

const AGENT_COLOR: Record<string, string> = {
  ideador: '#a855f7', rag: '#06b6d4', coder: '#3b82f6', sandbox: '#10b981',
  analista: '#f97316', latex: '#ec4899', revisor: '#ef4444', system: '#3b82f6',
};

const TEXT_CLASS: Record<string, string> = {
  info: '', success: 'text-cyber-green', error: 'text-cyber-red', warning: 'text-cyber-yellow', thinking: 'text-cyber-purple italic',
};

const TABS: { key: TerminalTab; label: string }[] = [
  { key: 'all', label: '📋 Todo' },
  { key: 'thinking', label: '💭 Razonamiento' },
  { key: 'issues', label: '⚠️ Errores' },
];

const filterLogs = (logs: TerminalLog[], tab: TerminalTab) =>
  tab === 'all' ? logs
    : tab === 'thinking' ? logs.filter((l) => l.type === 'thinking')
      : logs.filter((l) => l.type === 'error' || l.type === 'warning');

export const AgentTerminal: React.FC<Props> = ({ logs, activeTab, onTabChange, onClear }) => {
  const visible = filterLogs(logs, activeTab);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: 'end' });
  }, [visible.length]);

  return (
    <div className="flex flex-col h-full bg-dark-secondary border-t border-dark-primary/40">
      <div className="flex items-center gap-0 border-b border-dark-primary/40 px-2">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => onTabChange(t.key)}
            className={`px-4 py-2.5 text-[11px] font-medium transition-all border-b-2 ${
              activeTab === t.key ? 'text-cyber-blue border-cyber-blue' : 'text-gray-500 border-transparent hover:text-gray-300'
            }`}
          >
            {t.label}
          </button>
        ))}
        <button onClick={onClear} className="ml-auto text-[10px] text-gray-600 hover:text-red-400 transition-colors px-2">
          Limpiar
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-3 terminal-font text-[11px] leading-relaxed space-y-0.5">
        {visible.map((log) => {
          const color = AGENT_COLOR[log.agent] ?? '#94a3b8';
          return (
            <div key={log.id} className="flex items-start gap-2 animate-fade-in rounded px-1 -mx-1 hover:bg-white/[0.02]">
              <span className="text-gray-600 text-[10px] shrink-0">{log.timestamp}</span>
              <span className="shrink-0 px-1.5 py-0.5 rounded text-[9px] font-bold" style={{ backgroundColor: `${color}33`, color }}>
                {log.agent}
              </span>
              <span className={`${TEXT_CLASS[log.type] || 'text-gray-300'} flex-1 break-words`}>{log.text}</span>
            </div>
          );
        })}
        {visible.length === 0 && <div className="flex items-center justify-center h-full text-gray-600 text-sm">Sin registros todavía</div>}
        <div ref={endRef} />
      </div>
    </div>
  );
};

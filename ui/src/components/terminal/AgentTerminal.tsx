import React from 'react';
import type { TerminalLog, TerminalTab as TerminalTabType } from '@/types/api';

interface Props {
  logs: TerminalLog[];
  activeTab: TerminalTabType;
  onTabChange: (tab: TerminalTabType) => void;
  onClear: () => void;
}

const agentColors: Record<string, string> = {
  ideador: 'tag-purple', rag: 'tag-cyan', coder: 'tag-blue', sandbox: 'tag-green',
  analista: 'tag-orange', latex: 'tag-pink', revisor: 'tag-red', system: 'tag-blue',
};

const tagBg: Record<string, string> = {
  'tag-purple': 'rgba(168,85,247,0.2)', 'tag-cyan': 'rgba(6,182,212,0.2)', 'tag-blue': 'rgba(59,130,246,0.2)',
  'tag-green': 'rgba(16,185,129,0.2)', 'tag-orange': 'rgba(249,115,22,0.2)', 'tag-pink': 'rgba(236,72,153,0.2)',
  'tag-red': 'rgba(239,68,68,0.2)',
};

const tagColors: Record<string, string> = {
  'tag-purple': '#a855f7', 'tag-cyan': '#06b6d4', 'tag-blue': '#3b82f6',
  'tag-green': '#10b981', 'tag-orange': '#f97316', 'tag-pink': '#ec4899', 'tag-red': '#ef4444',
};

const textCls: Record<string, string> = {
  info: '', success: 'text-cyber-green', error: 'text-cyber-red', warning: 'text-cyber-yellow', thinking: 'text-cyber-purple italic',
};

export const AgentTerminal: React.FC<Props> = ({ logs, activeTab, onTabChange, onClear }) => {
  const tabIcons: Record<TerminalTabType, string> = { cot: '💭 CoT', logs: '📋 Logs', traces: '🔍 Traces' };

  return (
    <div className="flex flex-col h-full bg-dark-secondary border-t border-dark-primary/40">
      {/* Tabs */}
      <div className="flex items-center gap-0 border-b border-dark-primary/40 px-2">
        {(Object.entries(tabIcons) as [TerminalTabType, string][]).map(([tab, label]) => (
          <button key={tab} onClick={() => onTabChange(tab)}
            className={`px-4 py-2.5 text-[11px] font-medium transition-all border-b-2 ${activeTab === tab ? 'text-cyber-blue border-cyber-blue' : 'text-gray-500 border-transparent hover:text-gray-300'}`}>
            {label}
          </button>
        ))}
        <div className="ml-auto">
          <button onClick={onClear} className="text-[10px] text-gray-600 hover:text-red-400 transition-colors px-2">
            Limpiar
          </button>
        </div>
      </div>

      {/* Logs */}
      <div className="flex-1 overflow-y-auto p-3 terminal-font text-[11px] leading-relaxed space-y-0.5">
        {logs.map((log) => (
          <div key={log.id} className="flex items-start gap-2 animate-fade-in group hover:bg-white/[0.02] rounded px-1 -mx-1" style={{ animationDuration: '0.3s' }}>
            <span className="text-gray-600 text-[10px] shrink-0">{log.timestamp}</span>
            <span className="shrink-0 px-1.5 py-0.5 rounded text-[9px] font-bold" style={{ backgroundColor: tagBg[agentColors[log.agent]] || 'transparent', color: tagColors[agentColors[log.agent]] || '#94a3b8' }}>
              {log.agent}
            </span>
            <span className={`${textCls[log.type] || 'text-gray-300'} flex-1 break-all`}>{log.text}</span>
          </div>
        ))}
        {logs.length === 0 && (
          <div className="flex items-center justify-center h-full text-gray-600 text-sm">Sin logs yet</div>
        )}
      </div>
    </div>
  );
};

// CSS for fade-in animation injected once
const style = document.createElement('style');
style.textContent = '@keyframes fadeIn{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:none}}.animate-fade-in{animation:fadeIn 0.3s ease}';
if (!document.querySelector('#kiwisci-animations')) { style.id = 'kiwisci-animations'; document.head.appendChild(style); }

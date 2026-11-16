import React from 'react';
import { RotateCcw } from 'lucide-react';
import type { ResearchStep, StepStatus } from '@/types/api';
import type { InspectorTab } from '@/store/dashboard';

interface Props {
  steps: ResearchStep[];
  activeTab: InspectorTab;
  onTabChange: (tab: InspectorTab) => void;
  onToggleStep: (num: number) => void;
  expandedSteps: number[];
  /** Undefined when re-execution is not allowed (e.g. pipeline still running). */
  onReexecute?: (num: number) => void;
}

const statusDot: Record<StepStatus, string> = {
  done: 'bg-cyber-green shadow-lg shadow-cyber-green/50',
  progress: 'bg-cyber-blue animate-pulse shadow-lg shadow-cyber-blue/50',
  waiting: 'bg-gray-600',
  failed: 'bg-cyber-red shadow-lg shadow-cyber-red/50',
};

const stepNumBg: Record<StepStatus, string> = {
  done: 'bg-cyber-green/20 text-cyber-green',
  progress: 'bg-cyber-blue/20 text-cyber-blue',
  waiting: 'bg-gray-700/30 text-gray-500',
  failed: 'bg-cyber-red/20 text-cyber-red',
};

const TABS: { key: InspectorTab; label: string }[] = [
  { key: 'steps', label: 'Pasos' },
  { key: 'reasoning', label: 'Razonamiento' },
  { key: 'code', label: 'Código' },
];

const durationOf = (s: ResearchStep): string | null => {
  if (!s.startTime || !s.endTime) return null;
  const sec = (new Date(s.endTime).getTime() - new Date(s.startTime).getTime()) / 1000;
  return sec >= 0 ? `${sec.toFixed(1)}s` : null;
};

export const StepInspector: React.FC<Props> = ({ steps, activeTab, onTabChange, onToggleStep, expandedSteps, onReexecute }) => {
  const list =
    activeTab === 'reasoning' ? steps.filter((s) => s.justification)
      : activeTab === 'code' ? steps.filter((s) => s.codeSnippet)
        : steps;
  const forceOpen = activeTab !== 'steps';

  return (
    <div className="flex flex-col h-full">
      <div className="flex gap-0 border-b border-dark-primary/40 px-3">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => onTabChange(t.key)}
            className={`px-3 py-2 text-[11px] font-medium transition-all border-b-2 ${
              activeTab === t.key ? 'text-cyber-purple border-cyber-purple' : 'text-gray-500 border-transparent hover:text-gray-300'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {list.map((s) => {
          const open = forceOpen || expandedSteps.includes(s.num);
          const duration = durationOf(s);
          return (
            <div key={s.num} className="step-card">
              <div onClick={() => onToggleStep(s.num)} className="flex items-center gap-3 p-3 cursor-pointer hover:bg-white/[0.02]">
                <div className={`w-7 h-7 rounded-lg flex items-center justify-center text-xs font-bold ${stepNumBg[s.status]}`}>{s.num}</div>
                <div className="flex-1 min-w-0">
                  <div className="text-[12px] font-semibold text-gray-200 truncate">{s.name}</div>
                  <div className="text-[10px] text-gray-500">
                    {s.agent}
                    {duration && ` · ${duration}`}
                  </div>
                </div>
                <div className={`w-2 h-2 rounded-full ${statusDot[s.status]} shrink-0`} />
              </div>

              {open && (
                <div className="px-3 pb-3 border-t border-dark-primary/40 pt-2 space-y-2">
                  {s.justification && activeTab !== 'code' && (
                    <div className={`text-[11px] leading-relaxed pl-3 border-l-2 rounded-r-lg py-2 whitespace-pre-wrap break-words ${
                      s.status === 'failed' ? 'text-cyber-red border-cyber-red/50 bg-cyber-red/[0.05]' : 'text-gray-300 border-cyber-purple/50 bg-cyber-purple/[0.04]'
                    }`}>
                      <strong className={s.status === 'failed' ? 'text-cyber-red' : 'text-cyber-purple'}>
                        {s.status === 'failed' ? 'Error:' : 'Resultado:'}
                      </strong>{' '}
                      {s.justification}
                    </div>
                  )}
                  {s.codeSnippet && activeTab !== 'reasoning' && (
                    <pre className="terminal-font text-[10px] bg-dark-primary/60 rounded-lg p-2 text-cyber-cyan overflow-x-auto border border-dark-primary/40 whitespace-pre-wrap">
                      {s.codeSnippet}
                    </pre>
                  )}
                  {!s.justification && !s.codeSnippet && (
                    <div className="text-[11px] text-gray-600">
                      {s.status === 'waiting' ? 'Pendiente de ejecución' : s.status === 'progress' ? 'En ejecución…' : 'Sin detalles'}
                    </div>
                  )}
                  {onReexecute && (s.status === 'done' || s.status === 'failed') && (
                    <button
                      onClick={() => onReexecute(s.num)}
                      className="w-full flex items-center justify-center gap-1.5 py-2 border border-cyber-blue/40 text-cyber-blue rounded-lg text-[11px] font-semibold hover:bg-cyber-blue/[0.1] transition-all"
                    >
                      <RotateCcw className="w-3 h-3" /> Re-ejecutar paso {s.num}
                    </button>
                  )}
                </div>
              )}
            </div>
          );
        })}
        {list.length === 0 && <div className="text-center py-8 text-gray-600 text-sm">Nada que mostrar todavía</div>}
      </div>
    </div>
  );
};

import React from 'react';
import { RotateCcw } from 'lucide-react';

interface StepInfo {
  num: number;
  name: string;
  agent: string;
  status: 'done' | 'progress' | 'waiting' | 'failed';
  justification?: string;
  codeSnippet?: string;
}

interface Props {
  steps: StepInfo[];
  activeTab: string;
  onTabChange: (tab: string) => void;
  onToggleStep: (num: number) => void;
  expandedSteps: Set<number>;
  onReexecute: (num: number) => void;
}

const statusDot: Record<string, string> = {
  done: 'bg-cyber-green shadow-lg shadow-cyber-green/50', progress: 'bg-cyber-blue animate-pulse shadow-lg shadow-cyber-blue/50',
  waiting: 'bg-gray-600', failed: 'bg-cyber-red shadow-lg shadow-cyber-red/50',
};

const stepNumBg: Record<string, string> = {
  done: 'bg-cyber-green/20 text-cyber-green', progress: 'bg-cyber-blue/20 text-cyber-blue',
  waiting: 'bg-gray-700/30 text-gray-500', failed: 'bg-cyber-red/20 text-cyber-red',
};

export const StepInspector: React.FC<Props> = ({ steps, activeTab, onTabChange, onToggleStep, expandedSteps, onReexecute }) => (
  <div className="flex flex-col h-full">
    {/* Tabs */}
    <div className="flex gap-0 border-b border-dark-primary/40 px-3">
      {['steps', 'reasoning', 'code'].map(tab => (
        <button key={tab} onClick={() => onTabChange(tab)}
          className={`px-3 py-2 text-[11px] font-medium transition-all border-b-2 capitalize ${activeTab === tab ? 'text-cyber-purple border-cyber-purple' : 'text-gray-500 border-transparent hover:text-gray-300'}`}>
          {tab}
        </button>
      ))}
    </div>

    {/* Step list */}
    <div className="flex-1 overflow-y-auto p-3 space-y-2">
      {steps.map((s) => (
        <div key={s.num} className="step-card">
          <div onClick={() => onToggleStep(s.num)} className="flex items-center gap-3 p-3 cursor-pointer hover:bg-white/[0.02]">
            <div className={`w-7 h-7 rounded-lg flex items-center justify-center text-xs font-bold ${stepNumBg[s.status]}`}>
              {s.num}
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-[12px] font-semibold text-gray-200 truncate">{s.name}</div>
              <div className="text-[10px] text-gray-500">{s.agent}</div>
            </div>
            <div className={`w-2 h-2 rounded-full ${statusDot[s.status]} shrink-0`} />
          </div>

          {expandedSteps.has(s.num) && (
            <div className="px-3 pb-3 border-t border-dark-primary/40 pt-2 space-y-2">
              {s.justification && (
                <div className="text-[11px] text-gray-300 leading-relaxed pl-3 border-l-2 border-cyber-purple/50 bg-cyber-purple/[0.04] rounded-r-lg py-2">
                  <strong className="text-cyber-purple">Por qué:</strong> {s.justification}
                </div>
              )}
              {s.codeSnippet && (
                <pre className="terminal-font text-[10px] bg-dark-primary/60 rounded-lg p-2 text-cyber-cyan overflow-x-auto border border-dark-primary/40 whitespace-pre-wrap">
                  {s.codeSnippet}
                </pre>
              )}
              {s.status === 'done' && (
                <button onClick={() => onReexecute(s.num)} className="w-full flex items-center justify-center gap-1.5 py-2 border border-cyber-blue/40 text-cyber-blue rounded-lg text-[11px] font-semibold hover:bg-cyber-blue/[0.1] transition-all">
                  <RotateCcw className="w-3 h-3" /> Re-ejecutar Paso {s.num}
                </button>
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  </div>
);

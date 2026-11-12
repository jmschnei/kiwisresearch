import React from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';

interface Props {
  isOpen: boolean;
  onToggle: () => void;
}

export const ResultsPanel: React.FC<Props> = ({ isOpen, onToggle }) => (
  <div className={`bg-dark-secondary border-t border-dark-primary/40 transition-all duration-500 ease-in-out overflow-hidden ${isOpen ? 'h-[280px]' : 'h-0'}`}>
    {/* Header bar */}
    <div className="flex items-center justify-between px-4 py-2 border-b border-dark-primary/40 shrink-0">
      <span className="text-sm font-semibold text-cyber-green">✅ Resultados Finales — Paper NeurIPS 2026</span>
      <button onClick={onToggle} className="w-7 h-7 flex items-center justify-center rounded-lg border border-dark-primary/40 text-gray-400 hover:text-cyber-red transition-colors">
        {isOpen ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
      </button>
    </div>

    {/* Content */}
    {isOpen && (
      <div className="flex h-full overflow-hidden">
        {/* PDF preview mockup */}
        <div className="flex-1 flex items-center justify-center p-6 border-r border-dark-primary/40 overflow-auto bg-gradient-to-br from-white/[0.02] to-transparent">
          <div className="w-[220px] shrink-0 bg-white text-black rounded shadow-xl shadow-black/30 p-5 text-[7px] leading-relaxed font-serif">
            <div className="font-bold text-[9px] mb-1.5 text-center leading-tight">Efficient Neural Architecture Search via Reinforcement Learning for Edge Deployment</div>
            <div className="text-center text-gray-500 mb-3 text-[6px]">J. Morales*, A. Chen, R. Patel — DFKI Lab & MIT CSAIL</div>
            <div className="border-t border-gray-300 pt-2 mb-2 italic text-[6px] text-gray-600 leading-relaxed">
              <strong>Abstract.</strong> We present EAS-RL, a novel framework combining evolutionary algorithms with reinforcement learning for automatic discovery of neural architectures optimized for edge devices...
            </div>
            <p className="mb-1"><strong>I. INTRODUCTION</strong></p>
            <p className="mb-1 text-gray-600">The proliferation of edge computing has necessitated the development of neural architectures...</p>
            <p className="mb-1"><strong>II. METHODOLOGY</strong></p>
            <p className="mb-2 text-gray-600">Our proposed EAS-RL framework operates in three phases: (1) Search space definition via differentiable architecture parameters...</p>
            <div className="text-center p-1.5 bg-gray-50 rounded border border-gray-200 font-mono text-[6px]">
              Architecture: ConvBlock → DepthWiseSeparable → AttentionHead → ASPP<br />
              Params: 1.2M | FLOPs: 89M | Latency: 4.2ms | mAP@0.5: 0.847
            </div>
          </div>
        </div>

        {/* Peer review metrics */}
        <div className="w-[300px] p-4 overflow-y-auto">
          <div className="text-sm font-bold text-cyber-green mb-3">🏆 Peer Review Metrics</div>

          {[
            { label: 'Overall Score', value: '8.7', sub: 'Strong Accept', color: 'text-cyber-green' },
            { label: 'Novelty', value: '9.1', sub: 'Innovative RL formulation', color: 'text-cyber-cyan' },
            { label: 'Methodology', value: '8.4', sub: 'Solid ablation studies', color: 'text-cyber-blue' },
            { label: 'Clarity', value: '8.8', sub: 'Well-organized', color: 'text-cyber-purple' },
          ].map((m) => (
            <div key={m.label} className="metric-card mb-2">
              <div className="text-[10px] text-gray-500 uppercase tracking-wider">{m.label}</div>
              <div className={`text-2xl font-bold ${m.color} terminal-font mt-0.5`}>{m.value}<span className="text-xs text-gray-500 ml-1">/10</span></div>
              <div className="text-[10px] text-gray-500 mt-0.5">{m.sub}</div>
            </div>
          ))}

          {/* Reproducibility */}
          <div className="metric-card mb-2">
            <div className="text-[10px] text-gray-500 uppercase tracking-wider">Reproducibility</div>
            <div className="flex items-center gap-3 mt-1.5">
              <span className="text-xl font-bold text-cyber-yellow terminal-font">92%</span>
              <div className="flex-1 h-1.5 bg-dark-primary/60 rounded-full overflow-hidden">
                <div className="h-full w-[92%] bg-gradient-to-r from-cyber-yellow to-orange-400 rounded-full" />
              </div>
            </div>
          </div>

          {/* Consensus */}
          <div className="metric-card mb-3">
            <div className="text-[10px] text-gray-500 uppercase tracking-wider">Reviewer Consensus</div>
            <div className="flex gap-0.5 mt-1.5">
              {[1, 2, 3, 4, 0.5].map((s, i) => (
                <span key={i} className={`${s >= 0.7 ? 'text-cyber-yellow' : 'text-gray-600'} text-lg`}>★</span>
              ))}
            </div>
            <div className="text-[10px] text-gray-500 mt-1">3/3 Accept | 2 Strong Accept</div>
          </div>

          {/* Artifacts */}
          <div className="text-[10px] text-gray-500 mb-2">📦 Artefactos Generados</div>
          <div className="space-y-1.5">
            {['📊 23 Figuras SVG/PNG', '⚙️ Reproducibility Pack', '🗺️ Architecture Diagram'].map((a) => (
              <div key={a} className="bg-dark-card border border-dark-primary/40 rounded-md p-2 text-center text-[10px] text-gray-400">{a}</div>
            ))}
          </div>
        </div>
      </div>
    )}
  </div>
);

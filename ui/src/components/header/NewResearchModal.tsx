import React, { useState } from 'react';
import { Modal } from '@/components/common/Modal';

interface Props { isOpen: boolean; onClose: () => void; onLaunch: (data: any) => void; }

export const NewResearchModal: React.FC<Props> = ({ isOpen, onClose, onLaunch }) => {
  const [title, setTitle] = useState('');
  const [type, setType] = useState('paper');
  const [domain, setDomain] = useState('ml');
  const [hypothesis, setHypothesis] = useState('');
  const [selectedAgents, setSelectedAgents] = useState(new Set(['ideador', 'rag', 'coder', 'sandbox', 'analista', 'latex', 'revisor']));

  const allAgents = [
    { id: 'ideador', icon: '🧠', name: 'Ideador' },
    { id: 'rag', icon: '📚', name: 'RAG Bibliotecario' },
    { id: 'coder', icon: '💻', name: 'Coder' },
    { id: 'sandbox', icon: '⚙️', name: 'Sandbox' },
    { id: 'analista', icon: '📊', name: 'Analista' },
    { id: 'latex', icon: '📝', name: 'Redactor LaTeX' },
    { id: 'revisor', icon: '🔍', name: 'Revisor Adversarial' },
  ];

  const toggleAgent = (id: string) => {
    setSelectedAgents(prev => new Set(prev.has(id) ? [...prev].filter(a => a !== id) : [...prev, id]));
  };

  const handleLaunch = () => {
    onLaunch({ title, type, domain, hypothesis, agentIds: [...selectedAgents] });
    onClose();
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="🧪 Nueva Investigación" footer={
      <div className="flex justify-end gap-3">
        <button onClick={onClose} className="btn-ghost">Cancelar</button>
        <button onClick={handleLaunch} className="btn-primary flex items-center gap-2">🚀 Lanzar Investigación</button>
      </div>
    }>
      {/* Configuration */}
      <div className="mb-5">
        <div className="text-[11px] text-cyber-cyan uppercase tracking-wider font-semibold mb-3">📌 Configuración del Proyecto</div>
        <div className="space-y-3">
          <input className="form-field-input" placeholder="Título de la Investigación" value={title} onChange={e => setTitle(e.target.value)} />
          <div className="grid grid-cols-2 gap-3">
            <select className="form-field-select" value={type} onChange={e => setType(e.target.value)}>
              {['paper', 'survey', 'exploration', 'experiment', 'benchmark'].map(t => (
                <option key={t} value={t}>{t === 'paper' ? '📝 Artículo Completo' : t === 'survey' ? '📚 Survey Sistemática' : t === 'exploration' ? '🔍 Exploración de Líneas' : t === 'experiment' ? '🧪 Diseño Experimental' : '📊 Benchmark'} ({t})</option>
              ))}
            </select>
            <select className="form-field-select" value={domain} onChange={e => setDomain(e.target.value)}>
              {['ml', 'nlp', 'cv', 'graphs', 'rl', 'privacy', 'multimodal', 'edge'].map(d => (
                <option key={d} value={d}>{d.toUpperCase()}</option>
              ))}
            </select>
          </div>
          <textarea className="form-field-input resize-none" rows={3} placeholder="Hipótesis principal o descripción de la investigación..." value={hypothesis} onChange={e => setHypothesis(e.target.value)} />
        </div>
      </div>

      {/* Agent selection */}
      <div className="mb-5">
        <div className="text-[11px] text-cyber-cyan uppercase tracking-wider font-semibold mb-3">🤖 Selección de Agentes</div>
        <div className="flex flex-wrap gap-2">
          {allAgents.map(a => (
            <button key={a.id} onClick={() => toggleAgent(a.id)}
              className={`px-3 py-1.5 rounded-lg border text-xs transition-all font-medium ${selectedAgents.has(a.id) ? 'border-cyber-blue bg-cyber-blue/15 text-cyber-blue' : 'border-dark-primary/40 text-gray-500 hover:text-gray-300'}`}>
              {a.icon} {a.name}
            </button>
          ))}
        </div>
      </div>

      {/* Advanced params */}
      <div>
        <div className="text-[11px] text-cyber-cyan uppercase tracking-wider font-semibold mb-3">⚙️ Parámetros Avanzados</div>
        <div className="grid grid-cols-2 gap-3">
          <select className="form-field-select">
            {['o4', 'o3-mini-high', 'GPT-4o', 'Claude 4 Sonnet'].map(m => <option key={m}>{m}</option>)}
          </select>
          <input type="number" defaultValue={16000} className="form-field-input" min={4000} step={4000} />
          <input type="number" defaultValue={25} className="form-field-input" step={1} />
          <select className="form-field-select">
            {['fast', 'standard', 'deep', 'max'].map(d => (
              <option key={d}>{d === 'fast' ? '⚡ Rápido (3 iter.)' : d === 'standard' ? '📏 Estándar (8 iter.)' : d === 'deep' ? '🔬 Profundo (16 iter.)' : '💎 Máximo (32 iter.)'}</option>
            ))}
          </select>
        </div>
      </div>
    </Modal>
  );
};

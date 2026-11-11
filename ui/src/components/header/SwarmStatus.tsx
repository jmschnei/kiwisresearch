import React from 'react';

interface Props {
  active: number;
  total: number;
}

export const SwarmStatus: React.FC<Props> = ({ active, total }) => (
  <div className="flex items-center gap-3 px-4 py-2 bg-dark-tertiary rounded-full border border-dark-primary/40">
    <span className={`w-2.5 h-2.5 rounded-full ${active > 0 ? 'bg-cyber-green animate-pulse shadow-lg shadow-cyber-green/50' : 'bg-gray-600'}`} />
    <span className="text-sm text-gray-400">Swarm:</span>
    <span className={`terminal-font text-sm font-bold ${active > 0 ? 'text-cyber-green' : 'text-gray-500'}`}>
      {active}/{total} activos
    </span>
  </div>
);

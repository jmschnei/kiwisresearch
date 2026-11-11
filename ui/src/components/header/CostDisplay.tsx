import React from 'react';

interface Props {
  tokens: string;
  costUsd: string;
  uptime: string;
}

export const CostDisplay: React.FC<Props> = ({ tokens, costUsd, uptime }) => (
  <div className="flex items-center gap-8">
    <div className="flex flex-col items-center gap-1">
      <span className="text-[9px] text-gray-500 uppercase tracking-[1.5px]">Tokens</span>
      <span className="terminal-font text-lg font-bold text-cyber-cyan neon-text-blue">{tokens}</span>
    </div>
    <div className="w-px h-8 bg-dark-primary/60" />
    <div className="flex flex-col items-center gap-1">
      <span className="text-[9px] text-gray-500 uppercase tracking-[1.5px]">Costo</span>
      <span className="terminal-font text-lg font-bold text-cyber-green neon-text-green">{costUsd}</span>
    </div>
    <div className="w-px h-8 bg-dark-primary/60" />
    <div className="flex flex-col items-center gap-1">
      <span className="text-[9px] text-gray-500 uppercase tracking-[1.5px]">Uptime</span>
      <span className="terminal-font text-lg font-bold text-cyber-yellow">{uptime}</span>
    </div>
  </div>
);

import React from 'react';

interface Props {
  progress: number;
  color?: string;
  height?: number;
  showLabel?: boolean;
}

const gradients = {
  blue: 'from-cyber-blue to-cyber-cyan',
  green: 'from-cyber-green to-emerald-400',
  yellow: 'from-cyber-yellow to-orange-400',
  red: 'from-cyber-red to-pink-500',
  purple: 'from-cyber-purple to-cyber-pink',
};

export const ProgressBar: React.FC<Props> = ({ progress, color = 'blue', height = 6, showLabel = true }) => (
  <div className="flex items-center gap-3">
    <div className="progress-bar" style={{ height: `${height}px` }}>
      <div
        className={`progress-bar-fill bg-gradient-to-r ${gradients[color as keyof typeof gradients] || 'from-cyber-blue to-cyber-cyan'}`}
        style={{ width: `${Math.min(100, Math.max(0, progress))}%`, height: `${height}px` }}
      />
    </div>
    {showLabel && (
      <span className="terminal-font text-xs text-gray-400 min-w-[36px] text-right">
        {Math.round(progress)}%
      </span>
    )}
  </div>
);

import React from 'react';

export const Spinner: React.FC<{ label?: string }> = ({ label }) => (
  <div className="flex items-center justify-center gap-3 py-10 text-gray-500 text-sm">
    <span className="w-4 h-4 rounded-full border-2 border-cyber-blue border-t-transparent animate-spin" />
    {label}
  </div>
);

export const ErrorBox: React.FC<{ message: string; onRetry?: () => void }> = ({ message, onRetry }) => (
  <div className="glass-panel border-cyber-red/30 p-5 text-sm text-gray-300 flex items-center justify-between gap-4">
    <span>⚠️ {message}</span>
    {onRetry && (
      <button onClick={onRetry} className="btn-ghost !py-1.5 !px-3 text-xs">
        Reintentar
      </button>
    )}
  </div>
);

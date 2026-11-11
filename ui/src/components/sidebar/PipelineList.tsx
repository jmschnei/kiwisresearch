import React from 'react';
import { Badge } from '@/components/common/Badge';
import { ProgressBar } from '@/components/common/ProgressBar';
import type { PipelineJob, PipelineStatus } from '@/types/api';

interface Props {
  pipelines: PipelineJob[];
  activeId: string | null;
  filter: 'all' | 'active' | 'completed' | 'failed';
  onSelect: (id: string) => void;
  onFilterChange: (f: typeof filter) => void;
}

const statusBadge: Record<PipelineStatus, { label: string; variant: any }> = {
  active: { label: 'Activa', variant: 'blue' as const },
  paused: { label: 'Pausada', variant: 'yellow' as const },
  completed: { label: 'Completada', variant: 'green' as const },
  failed: { label: 'Fallida', variant: 'red' as const },
};

const progressColor: Record<PipelineStatus, string> = {
  active: 'blue', paused: 'yellow', completed: 'green', failed: 'red',
};

export const PipelineList: React.FC<Props> = ({ pipelines, activeId, filter, onSelect, onFilterChange }) => {
  const filtered = filter === 'all' ? pipelines : pipelines.filter((p) => p.status === filter);

  return (
    <div className="flex flex-col h-full">
      {/* Filter chips */}
      <div className="flex gap-1.5 px-3 py-2 border-b border-dark-primary/40">
        {(['all', 'active', 'completed', 'failed'] as const).map((f) => (
          <button key={f} onClick={() => onFilterChange(f)}
            className={`px-2.5 py-1 text-[10px] rounded-md border transition-all font-medium capitalize ${filter === f ? 'bg-dark-hover text-cyber-blue border-cyber-blue/40' : 'text-gray-500 border-transparent hover:text-gray-300'}`}>
            {f === 'all' ? 'Todas' : f === 'active' ? 'Activas' : f === 'completed' ? 'Completadas' : 'Fallidas'}
          </button>
        ))}
      </div>

      {/* Pipeline items */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {filtered.map((p) => (
          <div key={p.id} onClick={() => onSelect(p.id)}
            className={`pipeline-card ${activeId === p.id ? 'active' : p.status}`}
            style={{ borderTop: 'none', borderLeftWidth: 3, borderRadius: '10px' }}>
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-semibold text-gray-200 truncate max-w-[160px]">{p.name}</span>
              <Badge label={statusBadge[p.status].label} variant={statusBadge[p.status].variant} dot />
            </div>
            <p className="text-[11px] text-gray-500 mb-3 line-clamp-2">{p.description}</p>
            <ProgressBar progress={p.progress} color={progressColor[p.status]} height={4} showLabel />
            <div className="flex items-center justify-between mt-2.5 text-[10px] text-gray-600 terminal-font">
              <span>{p.tokensUsed}</span>
              <span>{p.elapsedTime}</span>
            </div>
          </div>
        ))}

        {filtered.length === 0 && (
          <div className="text-center py-8 text-gray-600 text-sm">No hay pipelines</div>
        )}
      </div>
    </div>
  );
};

import React, { useState } from 'react';
import { Badge } from '@/components/common/Badge';
import { ProgressBar } from '@/components/common/ProgressBar';
import { STATUS_BADGE } from '@/lib/format';
import type { PipelineJob } from '@/types/api';

type Filter = 'all' | 'active' | 'completed' | 'failed';

interface Props {
  pipelines: PipelineJob[];
  activeId: string | null;
  onSelect: (id: string) => void;
}

const FILTERS: { key: Filter; label: string }[] = [
  { key: 'all', label: 'Todas' },
  { key: 'active', label: 'Activas' },
  { key: 'completed', label: 'Hechas' },
  { key: 'failed', label: 'Fallidas' },
];

export const PipelineList: React.FC<Props> = ({ pipelines, activeId, onSelect }) => {
  const [filter, setFilter] = useState<Filter>('all');
  const filtered = filter === 'all' ? pipelines : pipelines.filter((p) => p.status === filter);

  return (
    <div className="flex flex-col h-full">
      <div className="flex gap-1 px-2 py-2 border-b border-dark-primary/40">
        {FILTERS.map((f) => (
          <button
            key={f.key}
            onClick={() => setFilter(f.key)}
            className={`px-1.5 py-1 text-[10px] rounded-md border transition-all font-medium ${
              filter === f.key ? 'bg-dark-hover text-cyber-blue border-cyber-blue/40' : 'text-gray-500 border-transparent hover:text-gray-300'
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {filtered.map((p) => (
          <div
            key={p.id}
            onClick={() => onSelect(p.id)}
            className={`pipeline-card ${activeId === p.id ? 'selected' : ''} ${p.status}`}
            style={{ borderRadius: 10 }}
          >
            <div className="flex items-center justify-between gap-2 mb-2">
              <span className="text-sm font-semibold text-gray-200 truncate">{p.name}</span>
              <Badge label={STATUS_BADGE[p.status].label} variant={STATUS_BADGE[p.status].variant} dot />
            </div>
            <ProgressBar progress={p.progress} color={STATUS_BADGE[p.status].bar} height={4} showLabel />
            <div className="flex items-center justify-between mt-2.5 text-[10px] text-gray-600 terminal-font">
              <span>{p.tokensUsed} tok</span>
              <span>{p.elapsedTime}</span>
            </div>
          </div>
        ))}
        {filtered.length === 0 && <div className="text-center py-8 text-gray-600 text-sm">No hay investigaciones</div>}
      </div>
    </div>
  );
};

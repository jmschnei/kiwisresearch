import React from 'react';
import { Sparkles } from 'lucide-react';

interface Props { onClick: () => void; }

export const NewResearchBtn: React.FC<Props> = ({ onClick }) => (
  <button onClick={onClick} className="btn-primary flex items-center gap-2">
    <Sparkles className="w-4 h-4" /> Nueva Investigación
  </button>
);

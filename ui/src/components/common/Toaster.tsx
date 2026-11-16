import React from 'react';
import { X } from 'lucide-react';
import { useDashboardStore } from '@/store/dashboard';

const tone = {
  info: 'border-cyber-blue/40 text-cyber-blue',
  success: 'border-cyber-green/40 text-cyber-green',
  error: 'border-cyber-red/40 text-cyber-red',
} as const;

export const Toaster: React.FC = () => {
  const toasts = useDashboardStore((s) => s.toasts);
  const dismiss = useDashboardStore((s) => s.dismissToast);
  return (
    <div className="fixed bottom-4 right-4 z-[2000] flex flex-col gap-2 w-[340px] max-w-[calc(100vw-2rem)]">
      {toasts.map((t) => (
        <div key={t.id} role="status" className={`glass-panel px-4 py-3 text-sm flex items-start gap-3 ${tone[t.kind]}`}>
          <span className="flex-1 text-gray-200">{t.text}</span>
          <button onClick={() => dismiss(t.id)} aria-label="Cerrar" className="text-gray-500 hover:text-gray-200">
            <X className="w-4 h-4" />
          </button>
        </div>
      ))}
    </div>
  );
};

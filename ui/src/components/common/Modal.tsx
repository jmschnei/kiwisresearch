import React, { useEffect } from 'react';

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
}

export const Modal: React.FC<ModalProps> = ({ isOpen, onClose, title, children, footer }) => {
  useEffect(() => {
    if (isOpen) document.body.style.overflow = 'hidden';
    else document.body.style.overflow = '';
    return () => { document.body.style.overflow = ''; };
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-content max-w-xl m-4" onClick={(e) => e.stopPropagation()}>
        <div className="sticky top-0 z-10 p-6 pb-0 bg-dark-secondary rounded-t-2xl">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-xl font-bold gradient-hero">{title}</h2>
            <button onClick={onClose} className="w-8 h-8 flex items-center justify-center rounded-lg bg-dark-tertiary border border-dark-primary/40 text-gray-400 hover:text-red-400 hover:border-red-500/30 transition-all text-lg">
              ×
            </button>
          </div>
        </div>
        <div className="p-6">{children}</div>
        {footer && <div className="sticky bottom-0 p-6 pt-4 bg-dark-secondary rounded-b-2xl border-t border-dark-primary/40">{footer}</div>}
      </div>
    </div>
  );
};

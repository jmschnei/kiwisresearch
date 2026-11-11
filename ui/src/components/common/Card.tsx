import React, { ReactNode } from 'react';

interface CardProps {
  children: ReactNode;
  className?: string;
  glow?: boolean;
}

export const Card: React.FC<CardProps> = ({ children, className = '', glow = false }) => (
  <div className={`bg-dark-card border border-dark-primary/40 rounded-xl p-4 ${glow ? 'glow-border' : ''} ${className}`}>
    {children}
  </div>
);

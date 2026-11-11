import React from 'react';

interface BadgeProps {
  label: string;
  variant?: 'blue' | 'cyan' | 'green' | 'yellow' | 'orange' | 'red' | 'purple' | 'pink' | 'gray';
  size?: 'sm' | 'md';
  dot?: boolean;
}

const colorMap: Record<BadgeProps['variant'], string> = {
  blue: 'bg-cyber-blue/20 text-cyber-blue border-cyber-blue/30',
  cyan: 'bg-cyber-cyan/20 text-cyber-cyan border-cyber-cyan/30',
  green: 'bg-cyber-green/20 text-cyber-green border-cyber-green/30',
  yellow: 'bg-cyber-yellow/20 text-cyber-yellow border-cyber-yellow/30',
  orange: 'bg-cyber-orange/20 text-cyber-orange border-cyber-orange/30',
  red: 'bg-cyber-red/20 text-cyber-red border-cyber-red/30',
  purple: 'bg-cyber-purple/20 text-cyber-purple border-cyber-purple/30',
  pink: 'bg-cyber-pink/20 text-cyber-pink border-cyber-pink/30',
  gray: 'bg-dark-hover text-gray-400 border-dark-primary/40',
};

export const Badge: React.FC<BadgeProps> = ({ label, variant = 'gray', size = 'sm', dot = false }) => (
  <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md border text-[9px] font-bold tracking-wide uppercase ${colorMap[variant]} ${size === 'md' ? 'text-[10px]' : ''}`}>
    {dot && <span className="w-1.5 h-1.5 rounded-full bg-current" />}
    {label}
  </span>
);

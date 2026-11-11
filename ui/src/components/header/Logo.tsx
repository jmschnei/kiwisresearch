import React from 'react';

export const Logo = () => (
  <div className="flex items-center gap-3">
    <div className="w-9 h-9 bg-gradient-to-br from-cyber-blue via-cyber-purple to-cyber-pink rounded-xl flex items-center justify-center text-lg shadow-lg shadow-cyber-blue/30">
      🧠
    </div>
    <div>
      <div className="gradient-hero font-bold text-lg leading-none">KiwiSci</div>
      <div className="text-[10px] text-gray-500 tracking-[2px] uppercase">AI Scientist Engine v3.2</div>
    </div>
  </div>
);

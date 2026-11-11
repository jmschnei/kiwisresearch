/**
 * Local persistent configuration store.
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface AppConfig {
  theme: 'dark' | 'cyber-dark';
  compactMode: boolean;
  showAgentIcons: boolean;
  graphAnimationSpeed: number; // 1-10
  autoReconnectWS: boolean;
  defaultModel: string;
}

export const useConfigStore = create<AppConfig>()(
  persist(
    () => ({
      theme: 'cyber-dark',
      compactMode: false,
      showAgentIcons: true,
      graphAnimationSpeed: 5,
      autoReconnectWS: true,
      defaultModel: 'o4',
    }),
    { name: 'kiwisci-config' },
  ),
);

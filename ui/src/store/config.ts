/**
 * Persisted user preferences (used as defaults by the new-research form).
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export interface AppConfig {
  defaultModel: string; // '' = use each agent's configured model
  defaultDepth: 'fast' | 'standard' | 'deep' | 'max';
  defaultBudgetUsd: number; // 0 = unlimited
  setPrefs: (p: Partial<Omit<AppConfig, 'setPrefs'>>) => void;
}

export const useConfigStore = create<AppConfig>()(
  persist(
    (set) => ({
      defaultModel: '',
      defaultDepth: 'standard',
      defaultBudgetUsd: 0,
      setPrefs: (p) => set(p),
    }),
    { name: 'kiwisci-config' },
  ),
);

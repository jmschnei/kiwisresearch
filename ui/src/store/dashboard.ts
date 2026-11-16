/**
 * Client-side UI state (live terminal logs, connection state, toasts, view toggles).
 * Server data (pipelines, steps, costs...) lives in React Query, not here.
 */

import { create } from 'zustand';
import type { TerminalLog, TerminalTab } from '@/types/api';
import type { WsState } from '@/services/websocket';

export type InspectorTab = 'steps' | 'reasoning' | 'code';
export interface Toast {
  id: string;
  kind: 'info' | 'success' | 'error';
  text: string;
}

const MAX_LOGS = 500;

interface DashboardState {
  wsState: WsState;
  setWsState: (s: WsState) => void;

  logs: Record<string, TerminalLog[]>;
  setLogs: (pipelineId: string, logs: TerminalLog[]) => void;
  addLog: (pipelineId: string, log: TerminalLog) => void;
  clearLogs: (pipelineId: string) => void;
  terminalTab: TerminalTab;
  setTerminalTab: (t: TerminalTab) => void;

  inspectorTab: InspectorTab;
  setInspectorTab: (t: InspectorTab) => void;
  expandedSteps: number[];
  toggleStep: (n: number) => void;

  toasts: Toast[];
  pushToast: (kind: Toast['kind'], text: string) => void;
  dismissToast: (id: string) => void;
}

export const useDashboardStore = create<DashboardState>((set) => ({
  wsState: 'disconnected',
  setWsState: (wsState) => set({ wsState }),

  logs: {},
  setLogs: (id, logs) => set((s) => ({ logs: { ...s.logs, [id]: logs.slice(-MAX_LOGS) } })),
  addLog: (id, log) =>
    set((s) => {
      const cur = s.logs[id] ?? [];
      if (cur.some((l) => l.id === log.id)) return s;
      return { logs: { ...s.logs, [id]: [...cur, log].slice(-MAX_LOGS) } };
    }),
  clearLogs: (id) => set((s) => ({ logs: { ...s.logs, [id]: [] } })),
  terminalTab: 'all',
  setTerminalTab: (terminalTab) => set({ terminalTab }),

  inspectorTab: 'steps',
  setInspectorTab: (inspectorTab) => set({ inspectorTab }),
  expandedSteps: [],
  toggleStep: (n) =>
    set((s) => ({
      expandedSteps: s.expandedSteps.includes(n) ? s.expandedSteps.filter((x) => x !== n) : [...s.expandedSteps, n],
    })),

  toasts: [],
  pushToast: (kind, text) => {
    const id = crypto.randomUUID();
    set((s) => ({ toasts: [...s.toasts, { id, kind, text }].slice(-4) }));
    setTimeout(() => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })), 5000);
  },
  dismissToast: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
}));

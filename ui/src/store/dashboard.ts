/**
 * Global dashboard state via Zustand (persisted).
 * Centralizes pipeline, swarm, terminal logs, and UI state.
 */

import { create } from 'zustand';
import type { PipelineJob, AgentNode, TerminalLog, PaperResult, SwarmHealth, CostSnapshot, StepStatus } from '@/types/api';

type SidebarView = 'pipelines' | 'artifacts' | 'settings';
type TerminalTabType = 'cot' | 'logs' | 'traces';
type InspectorTabType = 'steps' | 'reasoning' | 'code';
type GraphHoverState = AgentNode | null;

interface DashboardState {
  // ── Pipelines ──
  pipelines: PipelineJob[];
  activePipelineId: string | null;
  pipelineFilter: 'all' | 'active' | 'completed' | 'failed';
  sidebarView: SidebarView;
  setPipelines: (pipelines: PipelineJob[]) => void;
  setActivePipeline: (id: string) => void;
  setPipelineFilter: (filter: DashboardState['pipelineFilter']) => void;
  toggleSidebarView: () => void;

  // ── Swarm / Agents ──
  agents: AgentNode[];
  swarmHealth: SwarmHealth | null;
  setAgents: (agents: AgentNode[]) => void;
  updateAgentStatus: (agentId: string, status: AgentNode['status']) => void;
  setSwarmHealth: (health: SwarmHealth) => void;

  // ── Terminal Logs ──
  terminalLogs: TerminalLog[];
  activeTerminalTab: TerminalTabType;
  maxTerminalLines: number;
  addLog: (log: Omit<TerminalLog, 'id'>) => void;
  setActiveTerminalTab: (tab: TerminalTabType) => void;
  clearLogs: () => void;

  // ── Inspector / Steps ──
  steps: Array<{
    num: number;
    name: string;
    agent: string;
    status: StepStatus;
    justification?: string;
    codeSnippet?: string;
    artifacts: any[];
  }>;
  activeInspectorTab: InspectorTabType;
  expandedSteps: Set<number>;
  setSteps: (steps: typeof dashboardState.steps) => void;
  setActiveInspectorTab: (tab: InspectorTabType) => void;
  toggleStepExpansion: (num: number) => void;

  // ── Graph ──
  hoveredAgent: GraphHoverState;
  setHoveredAgent: (agent: AgentNode | null) => void;

  // ── Cost ──
  costSnapshot: CostSnapshot;
  setCostSnapshot: (snapshot: CostSnapshot) => void;

  // ── Results Panel ──
  showResultsPanel: boolean;
  paperResult: PaperResult | null;
  toggleResultsPanel: () => void;
  setPaperResult: (result: PaperResult) => void;

  // ── Modal ──
  showNewResearchModal: boolean;
  openNewResearchModal: () => void;
  closeNewResearchModal: () => void;
}

const defaultCostSnapshot: CostSnapshot = {
  tokensUsed: 2_847_391,
  costUsd: '$0.00',
  uptime: '00:00:00',
  snapshotAt: new Date().toISOString(),
};

// Mutable ref for steps so we can use Set in state
const dashboardState: DashboardState = {} as any;

export const useDashboardStore = create<DashboardState>((set, get) => ({
  // ── Initialize all defaults ──
  pipelines: [],
  activePipelineId: null,
  pipelineFilter: 'all',
  sidebarView: 'pipelines',
  agents: [],
  swarmHealth: null,
  terminalLogs: [],
  activeTerminalTab: 'cot',
  maxTerminalLines: 500,
  steps: [],
  activeInspectorTab: 'steps',
  expandedSteps: new Set(),
  hoveredAgent: null,
  costSnapshot: defaultCostSnapshot,
  showResultsPanel: false,
  paperResult: null,
  showNewResearchModal: false,

  // ── Pipelines ──
  setPipelines: (pipelines) => set({ pipelines }),
  setActivePipeline: (id) => set({ activePipelineId: id }),
  setPipelineFilter: (filter) => set({ pipelineFilter: filter }),
  toggleSidebarView: () =>
    set((s) => ({ sidebarView: s.sidebarView === 'pipelines' ? 'artifacts' : 'pipelines' })),

  // ── Swarm ──
  setAgents: (agents) => set({ agents }),
  updateAgentStatus: (agentId, status) =>
    set((s) => ({
      agents: s.agents.map((a) => (a.id === agentId ? { ...a, status } : a)),
    })),
  setSwarmHealth: (health) => set({ swarmHealth: health }),

  // ── Terminal ──
  addLog: (log) =>
    set((s) => ({
      terminalLogs: [...s.terminalLogs.slice(-s.maxTerminalLines), { ...log, id: crypto.randomUUID() }],
    })),
  setActiveTerminalTab: (tab) => set({ activeTerminalTab: tab }),
  clearLogs: () => set({ terminalLogs: [] }),

  // ── Inspector ──
  setSteps: (steps) => set({ steps }),
  setActiveInspectorTab: (tab) => set({ activeInspectorTab: tab }),
  toggleStepExpansion: (num) =>
    set((s) => {
      const expanded = new Set(s.expandedSteps);
      expanded.has(num) ? expanded.delete(num) : expanded.add(num);
      return { expandedSteps: expanded };
    }),

  // ── Graph ──
  setHoveredAgent: (agent) => set({ hoveredAgent: agent }),

  // ── Cost ──
  setCostSnapshot: (snapshot) => set({ costSnapshot: snapshot }),

  // ── Results ──
  toggleResultsPanel: () => set((s) => ({ showResultsPanel: !s.showResultsPanel })),
  setPaperResult: (result) => set({ paperResult: result }),

  // ── Modal ──
  openNewResearchModal: () => set({ showNewResearchModal: true }),
  closeNewResearchModal: () => set({ showNewResearchModal: false }),
}));

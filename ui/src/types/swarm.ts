export type AgentStatus = 'thinking' | 'executing' | 'waiting' | 'reviewing' | 'idle';

export interface AgentNode {
  id: string;
  name: string;
  icon: string;
  color: string;
  status: AgentStatus;
  position?: { x: number; y: number };
  velocity?: { x: number; y: number };
  metadata: AgentMetadata;
}

export interface AgentMetadata {
  tokensUsed: number;
  costUsd: number;
  startTime: string;
  lastActivity: string;
  outputItems: number;
  errorCount: number;
  isHealthy: boolean;
}

export type PipelineStatus = 'active' | 'paused' | 'completed' | 'failed';

export interface PipelineJob {
  id: string;
  name: string;
  description: string;
  status: PipelineStatus;
  progress: number;
  type: ResearchType;
  domain: ResearchDomain;
  tokensUsed: string;
  elapsedTime: string;
  budgetUsd: number;
  spentUsd: number;
  agents: AgentConfig[];
  createdAt: string;
  updatedAt: string;
}

export type ResearchType = 'paper' | 'survey' | 'exploration' | 'experiment' | 'benchmark';
export type ResearchDomain = 'ml' | 'nlp' | 'cv' | 'graphs' | 'rl' | 'privacy' | 'multimodal' | 'edge';

export interface AgentConfig {
  agentId: string;
  active: boolean;
  priority: number;
}

export type StepStatus = 'done' | 'progress' | 'waiting' | 'failed';

export interface ResearchStep {
  num: number;
  name: string;
  agent: string;
  status: StepStatus;
  justification?: string;
  codeSnippet?: string;
  startTime?: string;
  endTime?: string;
  artifacts: Artifact[];
}

export interface Artifact {
  id: string;
  type: 'pdf' | 'png' | 'svg' | 'csv' | 'json' | 'md';
  name: string;
  size: string;
  thumbnail?: string;
}

export type TerminalTab = 'cot' | 'logs' | 'traces';

export interface TerminalLog {
  id: string;
  timestamp: string;
  agent: string;
  tag: string;
  text: string;
  type: 'info' | 'success' | 'error' | 'warning' | 'thinking';
}

export interface PeerReviewMetric {
  name: string;
  score: number;
  maxScore: number;
  color: string;
  description: string;
}

export interface PaperResult {
  title: string;
  authors: string[];
  abstract: string;
  pdfUrl?: string;
  metrics: PeerReviewMetric[];
  overallScore: number;
  reviewConsensus: 'accepted' | 'weak_accept' | 'borderline' | 'rejected';
  artifacts: Artifact[];
}

export interface CostSnapshot {
  tokensUsed: number;
  costUsd: string;
  uptime: string;
  snapshotAt: string;
}

export interface SwarmHealth {
  totalAgents: number;
  activeAgents: number;
  healthyAgents: number;
  unhealthyAgents: number;
  lastHeartbeat: string;
}


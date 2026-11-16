export type AgentStatus = 'thinking' | 'executing' | 'waiting' | 'reviewing' | 'idle';

export interface AgentNode {
  id: string;
  name: string;
  icon: string;
  color: string;
  status: AgentStatus;
  position?: { x: number; y: number };
  velocity?: { x: number; y: number };
  size: number;
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
  error?: string | null;
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
  type: 'pdf' | 'png' | 'svg' | 'csv' | 'json' | 'md' | 'tex' | 'py';
  name: string;
  size: string;
  thumbnail?: string;
}

export type TerminalTab = 'all' | 'thinking' | 'issues';

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

export type ReviewConsensus = 'accepted' | 'weak_accept' | 'borderline' | 'rejected';

export interface PaperResult {
  title: string;
  authors: string[];
  abstract: string;
  pdfUrl?: string | null;
  metrics: PeerReviewMetric[];
  overallScore: number;
  reviewConsensus: ReviewConsensus;
  artifacts: Artifact[];
}

export interface CostSnapshot {
  tokensUsed: number;
  costUsd: string;
  uptime: string;
  snapshotAt: string;
  estimated?: boolean;
}

export interface SwarmHealth {
  totalAgents: number;
  activeAgents: number;
  healthyAgents: number;
  unhealthyAgents: number;
  lastHeartbeat: string;
}


export interface TerminalLogEntry extends TerminalLog {
  pipelineId?: string;
}

export interface BackendConfig {
  project: string;
  agents: Record<string, { model: string; provider: string; temperature: number; maxTokens: number; enabled: boolean }>;
  providers: Record<string, {
    name: string; type: string; defaultModel: string; baseUrl: string | null;
    models: string[]; available: boolean; apiKeyEnvVar: string | null;
  }>;
  sandbox: { mode: string; timeout_seconds: number; memory_mb: number; network_isolated: boolean };
  memory: { enabled: boolean; vector_store: string; persist_dir: string };
  pipeline: Record<string, number | null>;
}

export interface ReviewScores {
  metrics: PeerReviewMetric[];
  consensus: ReviewConsensus;
}

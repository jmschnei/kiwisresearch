// ─── Request DTOs (send to FastAPI) ───

export interface CreateResearchRequest {
  title: string;
  type: ResearchType;
  domain: ResearchDomain;
  hypothesis: string;
  agentIds: string[];
  model: string;
  maxTokensPerIteration: number;
  budgetUsd: number;
  depthLevel: 'fast' | 'standard' | 'deep' | 'max';
}

export interface ReexecuteStepRequest {
  pipelineId: string;
  stepNum: number;
  override?: Record<string, any>;
}

export interface UpdatePipelineStatusRequest {
  pipelineId: string;
  status: PipelineStatus;
  reason?: string;
}

// ─── Response DTOs (receive from FastAPI) ───

export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: ApiError;
  meta?: {
    requestId: string;
    timestamp: string;
    version: string;
  };
}

export interface ApiError {
  code: string;
  message: string;
  details?: Record<string, any>;
}

// WebSocket event types
export interface WsEvent {
  type: 'pipeline_update' | 'step_update' | 'log_entry' | 'agent_status_change' | 'cost_update' | 'paper_ready';
  payload: Record<string, any>;
  timestamp: string;
}

export interface PipelineUpdatePayload {
  pipelineId: string;
  progress: number;
  status: PipelineStatus;
  activeAgents: string[];
}

export interface StepUpdatePayload {
  pipelineId: string;
  stepNum: number;
  agent: string;
  status: StepStatus;
  output?: Record<string, any>;
}

export interface AgentStatusChangePayload {
  agentId: string;
  previousStatus: AgentStatus;
  newStatus: AgentStatus;
  reason?: string;
}

export interface CostUpdatePayload {
  pipelineId: string;
  tokensSinceLastUpdate: number;
  totalTokens: number;
  costUsd: string;
}


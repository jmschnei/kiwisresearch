import type { AgentNode, AgentStatus, PipelineStatus, ResearchStep } from '@/types/api';

export const AGENT_CATALOG = [
  { id: 'ideador', name: 'Ideador', icon: '🧠', color: '#a855f7', size: 42, running: 'thinking' },
  { id: 'rag', name: 'RAG Bibliotecario', icon: '📚', color: '#06b6d4', size: 38, running: 'executing' },
  { id: 'coder', name: 'Coder', icon: '💻', color: '#3b82f6', size: 40, running: 'executing' },
  { id: 'sandbox', name: 'Sandbox', icon: '⚙️', color: '#10b981', size: 36, running: 'executing' },
  { id: 'analista', name: 'Analista', icon: '📊', color: '#f97316', size: 38, running: 'executing' },
  { id: 'latex', name: 'Redactor LaTeX', icon: '📝', color: '#ec4899', size: 36, running: 'executing' },
  { id: 'revisor', name: 'Revisor Adversarial', icon: '🔍', color: '#ef4444', size: 40, running: 'reviewing' },
] as const satisfies readonly { id: string; name: string; icon: string; color: string; size: number; running: AgentStatus }[];

const emptyMeta = {
  tokensUsed: 0, costUsd: 0, startTime: '', lastActivity: '', outputItems: 0, errorCount: 0, isHealthy: true,
};

/** Backend step i runs on catalog agent i (same order as the pipeline). */
export function agentsFromSteps(steps: ResearchStep[] | undefined, pipelineStatus: PipelineStatus | undefined): AgentNode[] {
  return AGENT_CATALOG.map((a, i) => {
    const step = steps?.[i];
    let status: AgentStatus = 'idle';
    if (step?.status === 'progress') status = a.running;
    else if (step?.status === 'waiting' && pipelineStatus === 'active') status = 'waiting';
    return {
      id: a.id, name: a.name, icon: a.icon, color: a.color, size: a.size, status,
      metadata: { ...emptyMeta, isHealthy: step?.status !== 'failed', errorCount: step?.status === 'failed' ? 1 : 0 },
    };
  });
}

/**
 * Connects the WebSocket once for the whole app and translates backend events
 * into React Query invalidations and terminal log entries.
 */

import { useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { swarmWs } from '@/services/websocket';
import { useDashboardStore } from '@/store/dashboard';
import { queryKeys } from '@/hooks/useApi';
import type { TerminalLog } from '@/types/api';

const hhmmss = (iso: string) => {
  const d = new Date(iso);
  return isNaN(d.getTime()) ? iso : d.toTimeString().slice(0, 8);
};

/** Map a backend log (agent display name) to the terminal's agent color key. */
export const AGENT_KEY_BY_NAME: Record<string, string> = {
  Ideador: 'ideador',
  'RAG Bibliotecario': 'rag',
  Coder: 'coder',
  Sandbox: 'sandbox',
  Analista: 'analista',
  'Redactor LaTeX': 'latex',
  'Revisor Adversarial': 'revisor',
  Sistema: 'system',
};

export function toTerminalLog(raw: any): TerminalLog {
  return {
    id: raw.id,
    timestamp: hhmmss(raw.timestamp),
    agent: AGENT_KEY_BY_NAME[raw.agent] ?? raw.agent,
    tag: raw.tag ?? '',
    text: raw.text,
    type: raw.type,
  };
}

export function useLiveSync(): void {
  const qc = useQueryClient();
  const setWsState = useDashboardStore((s) => s.setWsState);
  const addLog = useDashboardStore((s) => s.addLog);

  useEffect(() => {
    const offStatus = swarmWs.onStatus((s) => {
      setWsState(s);
      if (s === 'connected') qc.invalidateQueries(); // resync anything missed while offline
    });
    const offEvents = swarmWs.subscribe((ev) => {
      const p: any = ev.payload;
      switch (ev.type) {
        case 'log_entry':
          if (p.pipelineId) addLog(p.pipelineId, toTerminalLog(p));
          break;
        case 'pipeline_update':
          qc.invalidateQueries({ queryKey: queryKeys.pipelines });
          qc.invalidateQueries({ queryKey: queryKeys.pipeline(p.pipelineId) });
          qc.invalidateQueries({ queryKey: queryKeys.agents });
          qc.invalidateQueries({ queryKey: queryKeys.health });
          if (p.status === 'completed' || p.status === 'failed') {
            qc.invalidateQueries({ queryKey: queryKeys.paper(p.pipelineId) });
            qc.invalidateQueries({ queryKey: queryKeys.review(p.pipelineId) });
            qc.invalidateQueries({ queryKey: queryKeys.artifacts(p.pipelineId) });
          }
          break;
        case 'step_update':
          qc.invalidateQueries({ queryKey: queryKeys.steps(p.pipelineId) });
          if (p.agent === 'Revisor Adversarial') {
            qc.invalidateQueries({ queryKey: queryKeys.review(p.pipelineId) });
            qc.invalidateQueries({ queryKey: queryKeys.paper(p.pipelineId) });
          }
          break;
        case 'cost_update':
          qc.invalidateQueries({ queryKey: queryKeys.costs() });
          qc.invalidateQueries({ queryKey: queryKeys.costs(p.pipelineId) });
          qc.invalidateQueries({ queryKey: queryKeys.breakdown(p.pipelineId) });
          break;
        case 'agent_status_change':
          qc.invalidateQueries({ queryKey: queryKeys.agents });
          break;
      }
    });
    swarmWs.connect();
    return () => {
      offStatus();
      offEvents();
    };
  }, [qc, setWsState, addLog]);
}

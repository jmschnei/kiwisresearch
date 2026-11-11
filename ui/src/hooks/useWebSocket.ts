/**
 * Hook for subscribing to WebSocket swarm events.
 * Handles connection lifecycle automatically.
 */

import { useEffect, useRef } from 'react';
import { swarmWs } from '@/services/websocket';
import { useDashboardStore } from '@/store/dashboard';

export function useWebSocketSync(): boolean {
  const setAgents = useDashboardStore((s) => s.setAgents);
  const updateAgentStatus = useDashboardStore((s) => s.updateAgentStatus);
  const addLog = useDashboardStore((s) => s.addLog);
  const setSwarmHealth = useDashboardStore((s) => s.setSwarmHealth);
  const connectedRef = useRef(false);

  useEffect(() => {
    // Connect on mount
    swarmWs.connect();

    // Agent status changes
    swarmWs.on('agent_status_change', (payload: any) => {
      updateAgentStatus(payload.agentId, payload.newStatus);
    });

    // Log entries via WS (real-time)
    swarmWs.on('log_entry', (payload: any) => {
      addLog({
        timestamp: payload.timestamp || new Date().toISOString(),
        agent: payload.agent,
        tag: payload.tag || '',
        text: payload.text,
        type: payload.type as any,
      });
    });

    // Swarm health updates
    swarmWs.on('pipeline_update', (payload: any) => {
      setSwarmHealth({
        totalAgents: 7,
        activeAgents: payload.activeAgents?.length ?? 0,
        healthyAgents: 7,
        unhealthyAgents: 0,
        lastHeartbeat: new Date().toISOString(),
      });
    });

    return () => {
      // Don't disconnect on unmount — it's a singleton
    };
  }, []);

  return swarmWs.isConnected;
}

export function useWsConnectionStatus(): 'connected' | 'disconnected' | 'reconnecting' {
  const [status, setStatus] = React.useState<'connected' | 'disconnected' | 'reconnecting'>('disconnected');

  useEffect(() => {
    swarmWs.onStatus(setStatus);
  }, []);

  return status;
}

// Need React import for the hook above to work properly - handled by react in same module
import * as React from 'react';

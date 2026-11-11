/**
 * Hook for D3 force-directed graph physics simulation.
 */

import { useEffect, useRef, useCallback } from 'react';
import * as d3 from 'd3';
import type { AgentNode } from '@/types/api';

export function useGraphPhysics(
  width: number,
  height: number,
  agents: AgentNode[],
  speedMultiplier: number = 1,
) {
  const simulationRef = useRef<d3.Simulation<any, any> | null>(null);

  const initGraph = useCallback(() => {
    if (simulationRef.current) {
      simulationRef.current.stop();
    }

    const nodes = agents.map((a) => ({ ...a, x: width / 2, y: height / 2 }));
    const links = [
      { source: 'swarm', target: agents[0]?.id },
      { source: 'swarm', target: agents[1]?.id },
      { source: 'swarm', target: agents[2]?.id },
      { source: 'swarm', target: agents[3]?.id },
      { source: 'swarm', target: agents[4]?.id },
      { source: 'swarm', target: agents[5]?.id },
      { source: 'swarm', target: agents[6]?.id },
    ].filter(Boolean);

    const simulation = d3
      .forceSimulation(nodes)
      .force(
        'link',
        d3.forceLink(links as any).id((d: any) => d.id).distance(180),
      )
      .force('charge', d3.forceManyBody().strength(-400))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide().radius(60))
      .alphaDecay(0.01 * speedMultiplier);

    simulationRef.current = simulation;
    return () => simulation.stop();
  }, [width, height, agents, speedMultiplier]);

  useEffect(() => {
    const cleanup = initGraph();
    return cleanup;
  }, [initGraph]);

  return simulationRef;
}

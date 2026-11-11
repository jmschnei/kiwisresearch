import React, { useRef, useEffect, useCallback } from 'react';
import type { AgentNode } from '@/types/api';

interface Props {
  agents: AgentNode[];
  hoveredAgent: AgentNode | null;
  onHover: (agent: AgentNode | null) => void;
}

const STATUS_COLORS: Record<string, string> = {};

export const AgentGraph: React.FC<Props> = ({ agents, hoveredAgent, onHover }) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animRef = useRef<number>(0);
  const timeRef = useRef(0);
  const positionsRef = useRef<Map<string, { x: number; y: number }>>(new Map());

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d')!;
    const container = canvas.parentElement!;

    const resize = () => {
      canvas.width = container.clientWidth * window.devicePixelRatio;
      canvas.height = container.clientHeight * window.devicePixelRatio;
      canvas.style.width = `${container.clientWidth}px`;
      canvas.style.height = `${container.clientHeight}px`;
      ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
    };
    resize();
    window.addEventListener('resize', resize);

    // Initialize positions in circle
    const w = container.clientWidth;
    const h = container.clientHeight;
    const cx = w / 2, cy = h / 2;
    const r = Math.min(w, h) * 0.3;
    agents.forEach((a, i) => {
      const angle = (i / agents.length) * Math.PI * 2 - Math.PI / 2;
      positionsRef.current.set(a.id, { x: cx + r * Math.cos(angle), y: cy + r * Math.sin(angle) });
    });

    // Color hex map
    Object.assign(STATUS_COLORS, {
      ideador: '#a855f7', rag: '#06b6d4', coder: '#3b82f6', sandbox: '#10b981',
      analista: '#f97316', latex: '#ec4899', revisor: '#ef4444',
    });

    const draw = (t: number) => {
      timeRef.current = t;
      ctx.clearRect(0, 0, canvas.width / window.devicePixelRatio, canvas.height / window.devicePixelRatio);

      // Background gradient
      const bgGrad = ctx.createRadialGradient(cx, cy, 0, cx, cy, Math.max(w, h) / 2);
      bgGrad.addColorStop(0, 'rgba(59,130,246,0.03)');
      bgGrad.addColorStop(1, 'transparent');
      ctx.fillStyle = '#0a0e1a';
      ctx.fillRect(0, 0, w, h);
      ctx.fillStyle = bgGrad;
      ctx.fillRect(0, 0, w, h);

      // Grid
      ctx.strokeStyle = 'rgba(42,58,92,0.2)';
      ctx.lineWidth = 0.5;
      for (let x = 0; x < w; x += 60) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, h); ctx.stroke(); }
      for (let y = 0; y < h; y += 60) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke(); }

      const centerNode = { x: cx, y: cy };

      // Draw inter-agent connections
      const edgePairs = [[0,2],[1,3],[3,4],[4,5],[5,6]];
      edgePairs.forEach(([i, j]) => {
        const ai = agents[i], aj = agents[j];
        const pi = positionsRef.current.get(ai.id)!;
        const pj = positionsRef.current.get(aj.id)!;
        ctx.beginPath(); ctx.moveTo(pi.x, pi.y); ctx.lineTo(pj.x, pj.y);
        const active = ai.status === 'thinking' || ai.status === 'executing' || aj.status === 'thinking' || aj.status === 'executing';
        ctx.strokeStyle = `rgba(59,130,246,${active ? 0.15 : 0.04})`;
        ctx.setLineDash([4, 4]); ctx.lineWidth = 1; ctx.stroke(); ctx.setLineDash([]);
      });

      // Draw center → agent connections + particles
      agents.forEach((agent, i) => {
        const color = STATUS_COLORS[agent.id] || '#3b82f6';
        let pos = positionsRef.current.get(agent.id)!;
        const isActive = agent.status === 'thinking' || agent.status === 'executing';
        const isHovered = hoveredAgent?.id === agent.id;

        // Animate position slightly
        if (isActive) {
          const pulse = Math.sin(t * 0.003 + i) * 12;
          pos = { x: pos.x + Math.cos(t * 0.002 + i * 0.7) * pulse, y: pos.y + Math.sin(t * 0.002 + i * 0.7) * pulse };
        }

        // Line to center
        ctx.beginPath(); ctx.moveTo(centerNode.x, centerNode.y); ctx.lineTo(pos.x, pos.y);
        ctx.strokeStyle = `rgba(${hexToRgb(color)}, ${isActive ? 0.3 : isHovered ? 0.4 : 0.1})`;
        ctx.lineWidth = isActive ? 2 : 1;
        if (isActive) { ctx.shadowColor = color; ctx.shadowBlur = 8; }
        ctx.stroke(); ctx.shadowBlur = 0;

        // Data particles
        if (isActive) {
          const pt = ((t * 0.001 + i * 0.3) % 1);
          const px = centerNode.x + (pos.x - centerNode.x) * pt;
          const py = centerNode.y + (pos.y - centerNode.y) * pt;
          ctx.beginPath(); ctx.arc(px, py, 2.5, 0, Math.PI * 2);
          ctx.fillStyle = color; ctx.shadowColor = color; ctx.shadowBlur = 8; ctx.fill(); ctx.shadowBlur = 0;
        }

        // Node glow
        const glowR = isHovered ? 55 : isActive ? 40 : 22;
        const glowAlpha = isHovered ? 0.4 : isActive ? 0.2 : 0.08;
        const gGrad = ctx.createRadialGradient(pos.x, pos.y, agent.size * 0.7, pos.x, pos.y, glowR);
        gGrad.addColorStop(0, `rgba(${hexToRgb(color)}, ${glowAlpha})`);
        gGrad.addColorStop(1, 'transparent');
        ctx.fillStyle = gGrad; ctx.beginPath(); ctx.arc(pos.x, pos.y, glowR, 0, Math.PI * 2); ctx.fill();

        // Node body
        const nGrad = ctx.createRadialGradient(pos.x - agent.size * 0.25, pos.y - agent.size * 0.25, 0, pos.x, pos.y, agent.size);
        nGrad.addColorStop(0, lighten(color, 30)); nGrad.addColorStop(1, darken(color, 30));
        ctx.beginPath(); ctx.arc(pos.x, pos.y, agent.size, 0, Math.PI * 2);
        ctx.fillStyle = nGrad; ctx.shadowColor = color; ctx.shadowBlur = isActive ? 15 : isHovered ? 12 : 6;
        ctx.fill(); ctx.shadowBlur = 0;

        // Border ring
        ctx.beginPath(); ctx.arc(pos.x, pos.y, agent.size, 0, Math.PI * 2);
        ctx.strokeStyle = isHovered ? color : `rgba(${hexToRgb(color)}, 0.6)`;
        ctx.lineWidth = isHovered ? 3 : 1.5; ctx.stroke();

        // Animated status ring
        if (isActive) {
          const sa = t * 0.004 + i;
          ctx.beginPath(); ctx.arc(pos.x, pos.y, agent.size + 4, sa, sa + Math.PI * 0.6);
          ctx.strokeStyle = color; ctx.lineWidth = 2; ctx.stroke();
        }

        // Icon
        ctx.font = `${agent.size * 0.8}px serif`; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
        ctx.fillText(agent.icon, pos.x, pos.y);

        // Labels
        ctx.font = `600 11px Inter, sans-serif`;
        ctx.fillStyle = isHovered ? '#fff' : '#94a3b8';
        ctx.fillText(agent.name, pos.x, pos.y + agent.size + 16);

        const statusLabel = statusLabels[agent.status];
        ctx.font = `10px JetBrains Mono, monospace`;
        ctx.fillStyle = color;
        ctx.textAlign = 'center';
        ctx.fillText(statusLabel, pos.x, pos.y + agent.size + 32);

        positionsRef.current.set(agent.id, { x: pos.x, y: pos.y });
      });

      // Center node (SWARM)
      ctx.beginPath(); ctx.arc(cx, cy, 28, 0, Math.PI * 2);
      const cxGrad = ctx.createRadialGradient(cx, cy, 0, cx, cy, 28);
      cxGrad.addColorStop(0, 'rgba(59,130,246,0.5)'); cxGrad.addColorStop(1, 'rgba(59,130,246,0.1)');
      ctx.fillStyle = cxGrad; ctx.shadowColor = '#3b82f6'; ctx.shadowBlur = 20; ctx.fill(); ctx.shadowBlur = 0;
      ctx.font = '700 10px Inter, sans-serif'; ctx.textAlign = 'center';
      ctx.fillStyle = '#fff'; ctx.fillText('SWARM', cx, cy + 2);

      animRef.current = requestAnimationFrame(draw);
    };

    animRef.current = requestAnimationFrame(draw);
    return () => {
      window.removeEventListener('resize', resize);
      cancelAnimationFrame(animRef.current);
    };
  }, [agents, hoveredAgent]);

  // Mouse hover detection
  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    const canvas = canvasRef.current; if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left, my = e.clientY - rect.top;
    let found: AgentNode | null = null;
    agents.forEach(a => {
      const p = positionsRef.current.get(a.id);
      if (p && Math.hypot(mx - p.x, my - p.y) < a.size + 8) found = a;
    });
    onHover(found);
  }, [agents, onHover]);

  return <canvas ref={canvasRef} className="w-full h-full block cursor-crosshair" onMouseMove={handleMouseMove} onMouseLeave={() => onHover(null)} />;
};

const statusLabels: Record<string, string> = {
  thinking: '💭 Pensando...', executing: '⚡ Ejecutando', waiting: '⏳ Esperando', reviewing: '🔎 En revisión', idle: '😴 Inactivo',
};

function hexToRgb(hex: string) { const r = parseInt(hex.slice(1, 3), 16); const g = parseInt(hex.slice(3, 5), 16); const b = parseInt(hex.slice(5, 7), 16); return `${r},${g},${b}`; }
function lighten(hex: string, a: number) { let r = parseInt(hex.slice(1,3),16), g = parseInt(hex.slice(3,5),16), b = parseInt(hex.slice(5,7),16); return `rgb(${Math.min(255,r+a)},${Math.min(255,g+a)},${Math.min(255,b+a)})`; }
function darken(hex: string, a: number) { let r = Math.max(0,parseInt(hex.slice(1,3),16)-a), g = Math.max(0,parseInt(hex.slice(3,5),16)-a), b = Math.max(0,parseInt(hex.slice(5,7),16)-a); return `rgb(${r},${g},${b})`; }

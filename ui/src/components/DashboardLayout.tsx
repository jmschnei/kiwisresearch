import React, { useState } from 'react';
import { Logo } from '@/components/header/Logo';
import { CostDisplay } from '@/components/header/CostDisplay';
import { SwarmStatus } from '@/components/header/SwarmStatus';
import { NewResearchBtn } from '@/components/header/NewResearchBtn';
import { PipelineList } from '@/components/sidebar/PipelineList';
import { AgentGraph } from '@/components/pipeline-graph/AgentGraph';
import { AgentTerminal } from '@/components/terminal/AgentTerminal';
import { StepInspector } from '@/components/inspector/StepInspector';
import { ResultsPanel } from '@/components/results/ResultsPanel';
import { NewResearchModal } from '@/components/header/NewResearchModal';
import { useDashboardStore } from '@/store/dashboard';

interface Props {}

export const DashboardLayout: React.FC<Props> = () => {
  const [wsConnected, setWsConnected] = useState(false);

  // Store accessors
  const pipelines = useDashboardStore(s => s.pipelines);
  const activePipelineId = useDashboardStore(s => s.activePipelineId);
  const pipelineFilter = useDashboardStore(s => s.pipelineFilter);
  const agents = useDashboardStore(s => s.agents);
  const hoveredAgent = useDashboardStore(s => s.hoveredAgent);
  const setHoveredAgent = useDashboardStore(s => s.setHoveredAgent);
  const costSnapshot = useDashboardStore(s => s.costSnapshot);
  const terminalLogs = useDashboardStore(s => s.terminalLogs);
  const activeTerminalTab = useDashboardStore(s => s.activeTerminalTab);
  const setCostSnapshot = useDashboardStore(s => s.setCostSnapshot);
  const setActivePipeline = useDashboardStore(s => s.setActivePipeline);
  const setPipelineFilter = useDashboardStore(s => s.setPipelineFilter);
  const steps = useDashboardStore(s => s.steps);
  const activeInspectorTab = useDashboardStore(s => s.activeInspectorTab);
  const expandedSteps = useDashboardStore(s => s.expandedSteps);
  const setActiveInspectorTab = useDashboardStore(s => s.setActiveInspectorTab);
  const toggleStepExpansion = useDashboardStore(s => s.toggleStepExpansion);
  const showResultsPanel = useDashboardStore(s => s.showResultsPanel);
  const toggleResultsPanel = useDashboardStore(s => s.toggleResultsPanel);
  const showNewResearchModal = useDashboardStore(s => s.showNewResearchModal);
  const openNewResearchModal = useDashboardStore(s => s.openNewResearchModal);
  const closeNewResearchModal = useDashboardStore(s => s.closeNewResearchModal);

  // ── Lifecycle: initialize mock data ──
  React.useEffect(() => {
    // Seed agents
    useDashboardStore.setState({
      agents: [
        { id: 'ideador', name: 'Ideador', icon: '🧠', color: '#a855f7', status: 'thinking', size: 42, metadata: {} as any },
        { id: 'rag', name: 'RAG Bibliotecario', icon: '📚', color: '#06b6d4', status: 'executing', size: 38, metadata: {} as any },
        { id: 'coder', name: 'Coder', icon: '💻', color: '#3b82f6', status: 'executing', size: 40, metadata: {} as any },
        { id: 'sandbox', name: 'Sandbox', icon: '⚙️', color: '#10b981', status: 'executing', size: 36, metadata: {} as any },
        { id: 'analista', name: 'Analista', icon: '📊', color: '#f97316', status: 'waiting', size: 38, metadata: {} as any },
        { id: 'latex', name: 'Redactor LaTeX', icon: '📝', color: '#ec4899', status: 'waiting', size: 36, metadata: {} as any },
        { id: 'revisor', name: 'Revisor Adversarial', icon: '🔍', color: '#ef4444', status: 'reviewing', size: 40, metadata: {} as any },
      ] as any[],
    });

    // Seed pipelines
    useDashboardStore.setState({
      pipelines: [
        { id: 'p-001', name: 'NAS Edge Computing', description: 'Búsqueda de arquitectura neural para edge devices', status: 'active', progress: 67, type: 'experiment' as any, domain: 'edge' as any, tokensUsed: '1.2M', elapsedTime: '04:32:18', budgetUsd: 25, spentUsd: 16.8, agents: [], createdAt: '', updatedAt: '' },
        { id: 'p-002', name: 'Federated Privacy', description: 'FL con privacidad diferencial para datos médicos', status: 'active', progress: 43, type: 'paper' as any, domain: 'privacy' as any, tokensUsed: '847K', elapsedTime: '02:15:44', budgetUsd: 20, spentUsd: 8.6, agents: [], createdAt: '', updatedAt: '' },
        { id: 'p-003', name: 'Graph Transformer Survey', description: 'Survey de Graph Transformers en bioinformática', status: 'completed', progress: 100, type: 'survey' as any, domain: 'graphs' as any, tokensUsed: '2.1M', elapsedTime: '08:45:00', budgetUsd: 30, spentUsd: 29.1, agents: [], createdAt: '', updatedAt: '' },
        { id: 'p-004', name: 'Few-Shot Vision Paper', description: 'Artículo sobre meta-learning few-shot para CV', status: 'active', progress: 23, type: 'paper' as any, domain: 'cv' as any, tokensUsed: '312K', elapsedTime: '01:08:12', budgetUsd: 15, spentUsd: 3.4, agents: [], createdAt: '', updatedAt: '' },
        { id: 'p-005', name: 'RLHF Ablation Study', description: 'Estudio de ablación en RLHF para LLMs', status: 'failed', progress: 78, type: 'experiment' as any, domain: 'rl' as any, tokensUsed: '1.5M', elapsedTime: '—', budgetUsd: 20, spentUsd: 18.2, agents: [], createdAt: '', updatedAt: '' },
        { id: 'p-006', name: 'Diffusion Audio Gen', description: 'Modelos de difusión para generación de audio', status: 'completed', progress: 100, type: 'paper' as any, domain: 'multimodal' as any, tokensUsed: '3.4M', elapsedTime: '12:20:55', budgetUsd: 40, spentUsd: 39.7, agents: [], createdAt: '', updatedAt: '' },
      ],
    });

    // Seed steps
    useDashboardStore.setState({
      steps: [
        { num: 1, name: 'Formulación del Problema', agent: 'Ideador', status: 'done' as any, justification: 'Se descartó el enfoque de búsqueda aleatoria por su ineficiencia computacional. Se seleccionó NAS basado en RL con reward multi-objectivo.', codeSnippet: 'def formulate_problem(hypothesis):\n    space = search_space(ops=[DWConv, SEBlock, ASPP])\n    return MultiObjectiveSpace(space)', artifacts: [] },
        { num: 2, name: 'Revisión Bibliográfica', agent: 'RAG Bibliotecario', status: 'done' as any, justification: 'Se encontraron 347 papers relevantes en arXiv/ACL/NeurIPS. Las fuentes clave: Zoph & Le (2017), Liu et al. (2018) DARTS.', codeSnippet: '# Papers encontrados via RAG:\nquery = "neural architecture search edge"\ntop_papers = rag.search(query, sources=["arxiv"], n=50)', artifacts: [] },
        { num: 3, name: 'Implementación del Search Space', agent: 'Coder', status: 'done' as any, justification: 'El search space se implementó con differentiable operations para permitir gradient-based optimization.', codeSnippet: 'class CellBuilder:\n    def build(self):\n        ops = [DWConv(kernel=3), SEBlock(channels=64), MultiHeadASPP(rates=[1,2,4])]\n        return concat(ops)', artifacts: [] },
        { num: 4, name: 'Ejecución en Sandbox', agent: 'Sandbox', status: 'done' as any, justification: 'Se ejecutó 50 generaciones con batch=32 en GPU A100. Memoria pico: 12.4GB.', codeSnippet: '# Sandbox execution log:\nGen 50/50 | avg_reward=0.847\nMemory: 12.4/16 GB\nAccuracy: 94.2% (CIFAR-10)\nFLOPs: 89M', artifacts: [] },
        { num: 5, name: 'Análisis de Resultados', agent: 'Analista', status: 'progress' as any, justification: '', codeSnippet: '# Calculando Pareto frontier...\narch_id=347 → acc=94.2%, flops=89M', artifacts: [] },
        { num: 6, name: 'Escritura del Manuscrito', agent: 'Redactor LaTeX', status: 'waiting' as any, justification: '', codeSnippet: '', artifacts: [] },
        { num: 7, name: 'Revisión Adversarial', agent: 'Revisor Adversarial', status: 'waiting' as any, justification: '', codeSnippet: '', artifacts: [] },
        { num: 8, name: 'Compilación Final', agent: 'Sistema', status: 'waiting' as any, justification: '', codeSnippet: 'pdflatex paper.tex && bibtex paper.aux', artifacts: [] },
      ],
    });

    // Seed initial terminal logs
    const seedLogs = [
      { timestamp: '14:23:01', agent: 'ideador', tag: '', text: '💭 [CoT] Analizando el espacio de búsqueda... La hipótesis central sugiere que un enfoque híbrido EA+RL puede reducir la complejidad O(n²) a O(n log n). Descartando gradient-based NAS por su tendencia a soluciones simétricas.', type: 'thinking' as const },
      { timestamp: '14:23:15', agent: 'rag', tag: '', text: '📚 Consultando arXiv con embeddings de 347 papers. Top-k retrieval para "neural architecture search multi-objective edge". Saliencia promedio: 0.892.', type: 'info' as const },
      { timestamp: '14:23:22', agent: 'coder', tag: '', text: '💻 Generando código del search space con operations: [DWConv, SEBlock, ASPP, DepthWisePool]. Compilando module graph...', type: 'info' as const },
      { timestamp: '14:23:30', agent: 'sandbox', tag: '', text: '⚙️ Sandbox init → Docker container nvidia/cuda:12.4-runtime | torch=2.5.1 | GPU=A100-SXM4-80GB', type: 'info' as const },
      { timestamp: '14:23:45', agent: 'sandbox', tag: '', text: '⚡ Benchmark gen 23/50... Accuracy: 93.7% | FLOPs: 87M | Latency: 4.8ms → Reward: 0.831 ✓', type: 'success' as const },
    ];
    useDashboardStore.setState({ terminalLogs: seedLogs });

    // Cost update timer
    let tokens = 2_847_391;
    let cost = 0;
    const interval = setInterval(() => {
      tokens += Math.floor(Math.random() * 500) + 100;
      cost += tokens * 0.000003 - (tokens - 500) * 0.000003;
      const now = new Date();
      setCostSnapshot({
        tokensUsed: tokens.toLocaleString(),
        costUsd: '$' + (cost).toFixed(4),
        uptime: now.toTimeString().slice(0, 8),
        snapshotAt: now.toISOString(),
      });
    }, 2000);

    // WebSocket connection status
    const wsStatusInterval = setInterval(() => {
      setWsConnected(prev => Math.random() > 0.3 ? true : prev);
    }, 5000);

    return () => { clearInterval(interval); clearInterval(wsStatusInterval); };
  }, []);

  // ── Render ──
  return (
    <div className="flex flex-col h-screen w-screen bg-dark-primary text-gray-200 overflow-hidden">

      {/* ═══ HEADER ═══ */}
      <header className="h-[64px] shrink-0 bg-dark-secondary border-b border-dark-primary/40 flex items-center justify-between px-6 relative z-10">
        {/* Left: Logo */}
        <Logo />

        {/* Center: Cost tracking + Swarm status */}
        <div className="flex items-center gap-8">
          <CostDisplay tokens={costSnapshot.tokensUsed} costUsd={costSnapshot.costUsd} uptime={costSnapshot.uptime} />
          <SwarmStatus active={agents.filter(a => a.status !== 'idle').length} total={agents.length} />
        </div>

        {/* Right: New Research button */}
        <NewResearchBtn onClick={openNewResearchModal} />
      </header>

      {/* ═══ MAIN LAYOUT ═══ */}
      <div className="flex flex-1 overflow-hidden">

        {/* ── Sidebar (Pipelines) ── */}
        <aside className="w-[280px] shrink-0 bg-dark-secondary border-r border-dark-primary/40 flex flex-col">
          <div className="px-5 py-3.5 border-b border-dark-primary/40">
            <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-[1.5px]">📋 Pipelines</span>
            <span className="ml-3 text-[11px] text-gray-600">{pipelines.filter(p => p.status === 'active').length} activas</span>
          </div>
          <PipelineList pipelines={pipelines} activeId={activePipelineId} filter={pipelineFilter} onSelect={setActivePipeline} onFilterChange={setPipelineFilter} />
        </aside>

        {/* ── Center Area (Graph + Terminal) ── */}
        <main className="flex-1 flex flex-col overflow-hidden relative">
          {/* Graph container */}
          <div className="flex-1 relative overflow-hidden">
            <AgentGraph agents={agents} hoveredAgent={hoveredAgent} onHover={setHoveredAgent} />

            {/* Overlay title card */}
            <div className="absolute top-4 left-4 right-4 flex justify-between pointer-events-none">
              <div className="glass-panel px-5 py-3 pointer-events-auto">
                <div className="text-sm font-bold text-gray-100">🔬 Grafo Multiagente en Tiempo Real</div>
                <div className="text-[11px] text-gray-500 mt-0.5">Proyecto: Neural Architecture Search para Edge Computing</div>
              </div>

              {/* Agent legend */}
              <div className="glass-panel px-4 py-2 pointer-events-auto space-y-1.5">
                {agents.map(a => (
                  <div key={a.id} className="flex items-center gap-2 text-[11px] text-gray-400">
                    <span className="w-2 h-2 rounded-full" style={{ backgroundColor: a.color }} />
                    {a.name}
                  </div>
                ))}
              </div>
            </div>

            {/* Results toggle button */}
            <button onClick={toggleResultsPanel}
              className={`absolute bottom-[220px] right-4 z-50 flex items-center gap-1.5 px-3 py-1.5 glass-panel text-xs font-medium transition-all cursor-pointer ${showResultsPanel ? 'text-cyber-green border-cyber-green/40' : 'text-gray-400 hover:text-cyber-green hover:border-cyber-green/30'}`}>
              📄 {showResultsPanel ? 'Ocultar' : 'Ver'} Resultados
            </button>
          </div>

          {/* Terminal */}
          <div className="h-[200px] shrink-0">
            <AgentTerminal logs={terminalLogs} activeTab={activeTerminalTab} onTabChange={useDashboardStore.getState().setActiveTerminalTab} onClear={() => useDashboardStore.getState().clearLogs()} />
          </div>

          {/* Results Panel (conditionally visible) */}
          <ResultsPanel isOpen={showResultsPanel} onToggle={toggleResultsPanel} />
        </main>

        {/* ── Right Inspector Panel ── */}
        <aside className="w-[340px] shrink-0 bg-dark-secondary border-l border-dark-primary/40 flex flex-col">
          <div className="px-5 py-3.5 border-b border-dark-primary/40 flex items-center justify-between">
            <span className="text-sm font-semibold text-gray-200">🔍 Inspector de Pasos</span>
            <span className="text-[10px] text-gray-500 terminal-font">{steps.find(s => s.status === 'progress')?.num || 5} de {steps.length}</span>
          </div>
          <StepInspector steps={steps} activeTab={activeInspectorTab} onTabChange={setActiveInspectorTab} onToggleStep={toggleStepExpansion} expandedSteps={expandedSteps} onReexecute={(n) => {}} />
        </aside>

      </div>

      {/* ═══ NEW RESEARCH MODAL ═══ */}
      <NewResearchModal isOpen={showNewResearchModal} onClose={closeNewResearchModal} onLaunch={() => {
        // Mock launch: add new pipeline
        const newId = `p-${String(Date.now()).slice(-6)}`;
        useDashboardStore.setState({
          pipelines: [
            ...useDashboardStore.getState().pipelines,
            { id: newId, name: 'Nova Investigació', description: 'Nueva investigación en proceso...', status: 'active' as any, progress: 0, type: 'paper' as any, domain: 'ml' as any, tokensUsed: '0', elapsedTime: '00:00:00', budgetUsd: 25, spentUsd: 0, agents: [], createdAt: new Date().toISOString(), updatedAt: new Date().toISOString() },
          ],
        });
      }} />

    </div>
  );
};

"""LangGraph-based research pipeline orchestrator."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class PipelinePhase(str, Enum):
    """Phases in the research lifecycle."""
    HYPOTHESIS = "hypothesis"
    LITERATURE = "literature"
    EXPERIMENT_DESIGN = "experiment_design"
    EXECUTION = "execution"
    ANALYSIS = "analysis"
    PAPER_WRITING = "paper_writing"
    PEER_REVIEW = "peer_review"
    REVISION = "revision"
    COMPLETE = "complete"


@dataclass
class PipelineState:
    """Central state shared across all pipeline nodes."""
    research_topic: str = ""
    phase: PipelinePhase = PipelinePhase.HYPOTHESIS
    current_step: int = 0
    total_steps: int = 0
    
    # Data carried between phases
    hypothesis: str = ""
    literature_review: dict = field(default_factory=dict)
    experiment_plan: dict = field(default_factory=dict)
    execution_results: dict[str, Any] = field(default_factory=dict)
    analysis: dict = field(default_factory=dict)
    paper_draft: dict = field(default_factory=dict)
    review_feedback: list[dict] = field(default_factory=list)
    
    # Metadata
    artifacts: dict[str, str] = field(default_factory=dict)
    timeline: list[dict] = field(default_factory=list)  # {phase, step, duration, status}
    errors: list[dict] = field(default_factory=list)
    
    def log_step(self, phase: PipelinePhase, step: int, status: str, duration: float):
        self.timeline.append({
            "phase": phase.value,
            "step": step,
            "status": status,
            "duration_seconds": round(duration, 2),
            "timestamp": time.time(),
        })
    
    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}
    
    @classmethod
    def from_dict(cls, d: dict) -> "PipelineState":
        return cls(**d)


@dataclass
class PipelineNode:
    """A single node in the research pipeline DAG."""
    name: str
    phase: PipelinePhase
    func: Callable[[PipelineState], Any]  # async function
    depends_on: list[PipelinePhase] = field(default_factory=list)
    retry_count: int = 0
    max_retries: int = 2
    
    async def execute(self, state: PipelineState) -> PipelineState:
        """Execute this node with retry logic."""
        start = time.monotonic()
        
        for attempt in range(self.max_retries + 1):
            try:
                logger.info(f"[{self.name}] Phase {self.phase.value} - Attempt {attempt + 1}")
                await self.func(state)
                duration = time.monotonic() - start
                state.log_step(self.phase, self.retry_count, "success", duration)
                logger.info(f"[{self.name}] Completed in {duration:.2f}s")
                return state
            
            except Exception as e:
                duration = time.monotonic() - start
                if attempt < self.max_retries:
                    state.log_step(self.phase, attempt, "retry", duration)
                    logger.warning(f"[{self.name}] Attempt {attempt + 1} failed: {e}. Retrying...")
                    self.retry_count += 1
                    await asyncio.sleep(min(2 ** attempt, 10))  # Exponential backoff
                else:
                    state.log_step(self.phase, attempt, "failed", duration)
                    state.errors.append({
                        "node": self.name,
                        "phase": self.phase.value,
                        "error": str(e),
                        "attempts": self.max_retries + 1,
                    })
                    logger.error(f"[{self.name}] All {self.max_retries + 1} attempts failed: {e}")
                    raise
        
        return state


class ResearchPipeline:
    """Orchestrates the full research lifecycle as a directed acyclic graph."""

    def __init__(
        self,
        settings=None,
        agent_factory: Optional[Callable[[str], Any]] = None,
        sandbox=None,
    ):
        self._settings = settings
        self._agent_factory = agent_factory
        self._sandbox = sandbox
        self._nodes: list[PipelineNode] = []
        self._state = PipelineState()
    
    def add_node(
        self,
        name: str,
        phase: PipelinePhase,
        func: Callable[[PipelineState], Any],
        depends_on: list[PipelinePhase] | None = None,
        max_retries: int = 2,
    ) -> "ResearchPipeline":
        """Add a node to the pipeline DAG."""
        node = PipelineNode(
            name=name,
            phase=phase,
            func=func,
            depends_on=depends_on or [],
            max_retries=max_retries,
        )
        self._nodes.append(node)
        return self
    
    def build_default_pipeline(self):
        """Build the standard research pipeline."""
        # Phase 1: Hypothesis Generation
        self.add_node(
            "generate_hypothesis",
            PipelinePhase.HYPOTHESIS,
            self._run_hypothesis_generation,
        )
        
        # Phase 2: Literature Review (depends on hypothesis)
        self.add_node(
            "conduct_literature_review",
            PipelinePhase.LITERATURE,
            self._run_literature_review,
            depends_on=[PipelinePhase.HYPOTHESIS],
        )
        
        # Phase 3: Experiment Design (depends on literature review + hypothesis)
        self.add_node(
            "design_experiment",
            PipelinePhase.EXPERIMENT_DESIGN,
            self._run_experiment_design,
            depends_on=[PipelinePhase.LITERATURE, PipelinePhase.HYPOTHESIS],
        )
        
        # Phase 4: Experiment Execution (depends on experiment design)
        self.add_node(
            "execute_experiment",
            PipelinePhase.EXECUTION,
            self._run_experiment_execution,
            depends_on=[PipelinePhase.EXPERIMENT_DESIGN],
        )
        
        # Phase 5: Analysis (depends on execution)
        self.add_node(
            "analyze_results",
            PipelinePhase.ANALYSIS,
            self._run_analysis,
            depends_on=[PipelinePhase.EXECUTION],
        )
        
        # Phase 6: Paper Writing (depends on analysis)
        self.add_node(
            "write_paper",
            PipelinePhase.PAPER_WRITING,
            self._run_paper_writing,
            depends_on=[PipelinePhase.ANALYSIS],
        )
        
        # Phase 7: Peer Review (depends on paper writing)
        self.add_node(
            "peer_review",
            PipelinePhase.PEER_REVIEW,
            self._run_peer_review,
            depends_on=[PipelinePhase.PAPER_WRITING],
        )
        
        return self
    
    async def run(self, research_topic: str) -> PipelineState:
        """Execute the full pipeline for a given research topic."""
        self._state = PipelineState(research_topic=research_topic)
        
        # Topological sort based on dependencies
        sorted_nodes = self._topological_sort()
        
        logger.info(f"Starting research pipeline for: {research_topic}")
        start_time = time.monotonic()
        
        for node in sorted_nodes:
            self._state.phase = node.phase
            await node.execute(self._state)
        
        self._state.phase = PipelinePhase.COMPLETE
        total_duration = time.monotonic() - start_time
        
        logger.info(f"Pipeline complete. Total duration: {total_duration:.2f}s")
        return self._state
    
    def _topological_sort(self) -> list[PipelineNode]:
        """Topological sort of pipeline nodes by dependencies."""
        visited = set()
        result = []
        
        def visit(node: PipelineNode):
            if node.name in visited:
                return
            visited.add(node.name)
            for dep in node.depends_on:
                dep_node = next((n for n in self._nodes if n.phase == dep), None)
                if dep_node:
                    visit(dep_node)
            result.append(node)
        
        for node in self._nodes:
            visit(node)
        
        return result
    
    # --- Phase implementations ---
    
    async def _run_hypothesis_generation(self, state: PipelineState):
        from ..agents import IdeationAgent
        from ..config.agents import AgentConfig
        
        agent = IdeationAgent(
            llm_provider=None,  # Inject via factory
        )
        output = await agent.execute(state)
        if output.state.name == "COMPLETED" and output.data.get("hypotheses"):
            state.hypothesis = output.data["hypotheses"][0].get("hypothesis", "")
    
    async def _run_literature_review(self, state: PipelineState):
        from ..agents import LibrarianAgent
        
        agent = LibrarianAgent()
        output = await agent.execute(state)
        if output.state.name != "COMPLETED":
            raise RuntimeError("Literature review failed")
    
    async def _run_experiment_design(self, state: PipelineState):
        from ..agents import ExperimentArchitectAgent
        
        agent = ExperimentArchitectAgent()
        output = await agent.execute(state)
        if output.state.name != "COMPLETED":
            raise RuntimeError("Experiment design failed")
    
    async def _run_experiment_execution(self, state: PipelineState):
        from ..agents import EngineerAgent
        from ..execution.isolated_sandbox import IsolatedSandbox
        
        sandbox = self._sandbox or IsolatedSandbox()
        agent = EngineerAgent(sandbox=sandbox)
        output = await agent.execute(state)
        if output.state.name not in ("COMPLETED", "FAILED"):
            raise RuntimeError("Experiment execution failed")
    
    async def _run_analysis(self, state: PipelineState):
        from ..agents import DataAnalystAgent
        
        agent = DataAnalystAgent()
        output = await agent.execute(state)
        if output.state.name != "COMPLETED":
            raise RuntimeError("Data analysis failed")
    
    async def _run_paper_writing(self, state: PipelineState):
        from ..agents import WriterAgent
        
        agent = WriterAgent()
        output = await agent.execute(state)
        if output.state.name != "COMPLETED":
            raise RuntimeError("Paper writing failed")
    
    async def _run_peer_review(self, state: PipelineState):
        from ..agents import ReviewerAgent
        
        agent = ReviewerAgent()
        output = await agent.execute(state)
        if output.state.name != "COMPLETED":
            raise RuntimeError("Peer review failed")

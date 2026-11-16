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
    revision_round: int = 0  # 0 = first draft; n = n-th revision after peer review
    paper_history: list[dict] = field(default_factory=list)  # one entry per paper version
    step_outputs: dict[str, dict] = field(default_factory=dict)  # role -> AgentOutput.to_dict()
    
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
        known = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        if "phase" in known:
            known["phase"] = PipelinePhase(known["phase"])
        return cls(**known)


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
        self._sandbox = sandbox
        # agent_factory: callable taking a role name and returning an agent.
        # Default: build agents from settings (provider + model per agent).
        if agent_factory is None:
            from .agent_factory import AgentFactory
            factory = AgentFactory(settings, sandbox=sandbox)
            agent_factory = factory.create
            self._default_factory = factory
        self._agent_factory = agent_factory
        self._nodes: list[PipelineNode] = []
        self._state = PipelineState()
        self._listeners: list[Callable[[dict], None]] = []
        self._resume = asyncio.Event()
        self._resume.set()

    # --- Observability / control ---

    @property
    def state(self) -> PipelineState:
        return self._state

    def add_listener(self, callback: Callable[[dict], None]) -> None:
        """Register a sync callback receiving step events (step_started/finished/failed/skipped)."""
        self._listeners.append(callback)

    def _emit(self, event_type: str, **data) -> None:
        event = {"type": event_type, **data}
        for cb in self._listeners:
            try:
                cb(event)
            except Exception:  # a broken listener must never break the pipeline
                logger.exception("Pipeline listener failed")

    def pause(self) -> None:
        """Pause before the next step starts (a running step is allowed to finish)."""
        self._resume.clear()

    def resume(self) -> None:
        self._resume.set()

    @property
    def paused(self) -> bool:
        return not self._resume.is_set()

    @property
    def phases(self) -> list[PipelinePhase]:
        return [n.phase for n in self._topological_sort()]
    
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
    
    async def run(self, research_topic: str, hypothesis: str = "") -> PipelineState:
        """Execute the full pipeline. A preset ``hypothesis`` skips hypothesis generation."""
        self._state = PipelineState(research_topic=research_topic, hypothesis=hypothesis)
        sorted_nodes = self._topological_sort()

        logger.info(f"Starting research pipeline for: {research_topic}")
        start_time = time.monotonic()

        for index, node in enumerate(sorted_nodes):
            await self._resume.wait()
            self._state.phase = node.phase
            self._state.current_step = index
            self._state.total_steps = len(sorted_nodes)
            if node.phase == PipelinePhase.HYPOTHESIS and hypothesis:
                self._emit("step_skipped", phase=node.phase, index=index, reason="hypothesis provided")
                continue
            await self._run_node(node, index)

        self._state.phase = PipelinePhase.COMPLETE
        logger.info(f"Pipeline complete. Total duration: {time.monotonic() - start_time:.2f}s")
        return self._state

    async def _run_node(self, node: PipelineNode, index: int) -> None:
        self._emit("step_started", phase=node.phase, index=index)
        started = time.monotonic()
        try:
            await node.execute(self._state)
        except Exception as e:
            self._emit("step_failed", phase=node.phase, index=index, error=str(e),
                       duration=time.monotonic() - started)
            raise
        self._emit("step_finished", phase=node.phase, index=index, duration=time.monotonic() - started)

    async def rerun_phase(self, phase: PipelinePhase) -> PipelineState:
        """Re-execute a single phase on the current state (e.g. after a failure)."""
        nodes = self._topological_sort()
        index, node = next(((i, n) for i, n in enumerate(nodes) if n.phase == phase), (None, None))
        if node is None:
            raise ValueError(f"No node for phase {phase}")
        self._state.phase = phase
        await self._run_node(node, index)
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

    def _agent(self, role: str):
        return self._agent_factory(role)

    async def _run_agent(self, role: str, state: PipelineState, key: Optional[str] = None):
        """Create the agent for ``role``, run it and record its output in the state under ``key`` (default: role)."""
        output = await self._agent(role).execute(state)
        state.step_outputs[key or role] = output.to_dict()
        return output

    async def _run_hypothesis_generation(self, state: PipelineState):
        output = await self._run_agent("ideation", state)
        if output.state.name != "COMPLETED":
            raise RuntimeError("Hypothesis generation failed")
        if output.data.get("hypotheses") and not state.hypothesis:
            state.hypothesis = output.data["hypotheses"][0].get("hypothesis", "")

    async def _run_literature_review(self, state: PipelineState):
        output = await self._run_agent("librarian", state)
        if output.state.name != "COMPLETED":
            raise RuntimeError("Literature review failed")

    async def _run_experiment_design(self, state: PipelineState):
        output = await self._run_agent("experiment_architect", state)
        if output.state.name != "COMPLETED":
            raise RuntimeError("Experiment design failed")

    async def _run_experiment_execution(self, state: PipelineState):
        if self._sandbox is None:
            from ..execution.isolated_sandbox import IsolatedSandbox
            self._sandbox = IsolatedSandbox()
            factory = getattr(self, "_default_factory", None)
            if factory is not None:
                factory._sandbox = self._sandbox
        output = await self._run_agent("engineer", state)
        if output.state.name not in ("COMPLETED", "FAILED"):
            raise RuntimeError("Experiment execution failed")

    async def _run_analysis(self, state: PipelineState):
        output = await self._run_agent("data_analyst", state)
        if output.state.name != "COMPLETED":
            raise RuntimeError("Data analysis failed")

    async def _run_paper_writing(self, state: PipelineState):
        # A fresh draft invalidates earlier reviews and revisions
        state.revision_round = 0
        state.review_feedback = []
        state.paper_history = []
        output = await self._run_agent("writer", state)
        if output.state.name != "COMPLETED":
            raise RuntimeError("Paper writing failed")

    def _review_limits(self) -> tuple[int, Optional[float]]:
        cfg = getattr(self._settings, "pipeline", None)
        rounds = getattr(cfg, "peer_review_critique_rounds", 2) if cfg else 2
        threshold = getattr(cfg, "auto_submit_threshold", None) if cfg else None
        return max(1, int(rounds)), threshold

    async def _run_peer_review(self, state: PipelineState):
        """Review the paper; while it is not accepted, have the writer revise it and review again.

        Runs at most ``pipeline.peer_review_critique_rounds`` reviews (1 = a single review, no revision).
        Stops early when the paper is accepted (verdict, or score >= ``auto_submit_threshold``) or when a
        review gives the writer nothing to act on (e.g. no LLM configured).
        """
        from .review_loop import decide

        max_rounds, threshold = self._review_limits()
        state.review_feedback = []
        state.revision_round = 0

        for round_no in range(1, max_rounds + 1):
            self._emit("review_round", phase=PipelinePhase.PEER_REVIEW, round=round_no, max_rounds=max_rounds)
            output = await self._run_agent("reviewer", state, key="reviewer" if round_no == 1 else f"reviewer_round_{round_no}")
            if output.state.name != "COMPLETED":
                raise RuntimeError("Peer review failed")

            decision = decide(state.review_feedback[-1], round_no, max_rounds, threshold)
            self._emit("review_decision", phase=PipelinePhase.PEER_REVIEW, round=round_no, max_rounds=max_rounds,
                       verdict=decision.verdict, score=decision.score, revise=decision.revise, reason=decision.reason)
            if not decision.revise:
                break

            state.revision_round = round_no
            self._emit("revision_started", phase=PipelinePhase.PEER_REVIEW, round=round_no)
            output = await self._run_agent("writer", state, key=f"writer_revision_{round_no}")
            if output.state.name != "COMPLETED":
                raise RuntimeError(f"Paper revision {round_no} failed")
            self._emit("revision_finished", phase=PipelinePhase.PEER_REVIEW, round=round_no)

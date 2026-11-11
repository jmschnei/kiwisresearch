"""Tests for the orchestrator."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from kiwis.orchestrator.pipeline import ResearchPipeline, PipelineState, PipelinePhase


def test_pipeline_state():
    state = PipelineState(research_topic="test", phase=PipelinePhase.HYPOTHESIS)
    assert state.research_topic == "test"
    
    state.log_step(PipelinePhase.LITERATURE, 1, "success", 2.5)
    assert len(state.timeline) == 1
    assert state.timeline[0]["phase"] == "literature"


def test_pipeline_builds_default():
    pipeline = ResearchPipeline()
    pipeline.build_default_pipeline()
    
    nodes = pipeline._nodes
    assert len(nodes) == 8  # 8 phases
    
    phases = [n.phase for n in nodes]
    assert PipelinePhase.HYPOTHESIS in phases
    assert PipelinePhase.PEER_REVIEW in phases

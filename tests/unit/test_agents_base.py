"""Tests for base agent classes."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from kiwis.agents.base import AgentOutput, AgentState, AgentContext


def test_agent_output_serialization():
    output = AgentOutput(
        agent_name="test-agent",
        state=AgentState.COMPLETED,
        data={"hypothesis": "Test hypothesis"},
    )
    
    d = output.to_dict()
    assert d["agent_name"] == "test-agent"
    assert d["state"] == AgentState.COMPLETED.value
    
    j = output.to_json()
    assert "test-agent" in j


def test_agent_context():
    ctx = AgentContext(
        research_topic="NLP",
        hypothesis="Transformers beat RNNs",
    )
    
    assert ctx.research_topic == "NLP"
    assert ctx.hypothesis == "Transformers beat RNNs"
    
    d = ctx.to_dict()
    restored = AgentContext.from_dict(d)
    assert restored.research_topic == "NLP"


def test_agent_states():
    assert AgentState.PENDING.value == "pending"
    assert AgentState.RUNNING.value == "running"
    assert AgentState.COMPLETED.value == "completed"
    assert AgentState.FAILED.value == "failed"

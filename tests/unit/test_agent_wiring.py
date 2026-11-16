"""Agents run with an LLM provider, and the pipeline wires providers from settings."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from kiwis.config.settings import Settings
from kiwis.models.base import ChatMessage, LLMProvider
from kiwis.models.factory import infer_provider_name
from kiwis.orchestrator.agent_factory import AgentFactory
from kiwis.orchestrator.pipeline import PipelineState, ResearchPipeline


class FakeLLM(LLMProvider):
    def __init__(self, reply: str):
        self.reply = reply
        self.calls = 0

    async def chat(self, messages, config):
        self.calls += 1
        return ChatMessage(role="assistant", content=self.reply)

    async def generate_text(self, prompt, system_prompt=None, config=None):
        return self.reply

    async def embed(self, texts):
        return [[0.0] for _ in texts]


JSON_REPLY = (
    '```json\n{"hypotheses": [{"title": "T", "hypothesis": "H1", "motivation": "", '
    '"feasibility": "", "novelty": "", "risk_level": "Low"}], '
    '"top_hypothesis_index": 0, "rationale": "r"}\n```'
)


def test_ideation_with_llm_sets_hypothesis():
    from kiwis.agents import IdeationAgent

    llm = FakeLLM(JSON_REPLY)
    state = PipelineState(research_topic="graphs")
    out = asyncio.run(IdeationAgent(llm_provider=llm).execute(state))
    assert out.state.name == "COMPLETED"
    assert state.hypothesis == "H1"
    assert state.research_topic == "graphs"  # topic must not be overwritten
    assert llm.calls == 1


def test_all_agents_run_with_llm():
    from kiwis.agents import (DataAnalystAgent, ExperimentArchitectAgent,
                              LibrarianAgent, ReviewerAgent, WriterAgent)

    for cls in (ExperimentArchitectAgent, DataAnalystAgent, WriterAgent, ReviewerAgent):
        llm = FakeLLM(JSON_REPLY)
        out = asyncio.run(cls(llm_provider=llm).execute(PipelineState(research_topic="x")))
        assert llm.calls >= 1, cls.__name__
        assert out.state.name == "COMPLETED", cls.__name__

    lib = LibrarianAgent(llm_provider=FakeLLM(JSON_REPLY))

    async def no_papers(*a, **k):
        return []

    lib._search_arxiv = no_papers
    lib._search_semantic_scholar = no_papers
    out = asyncio.run(lib.execute(PipelineState(research_topic="x")))
    assert out.state.name == "COMPLETED"


def test_infer_provider_name():
    assert infer_provider_name("claude-3-5-sonnet-20241022") == "anthropic"
    assert infer_provider_name("gpt-4o") == "openai"
    assert infer_provider_name("llama3.2") == "ollama"
    assert infer_provider_name("deepseek-chat") == "deepseek"


def test_factory_injects_model_config_and_provider(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    factory = AgentFactory(Settings.default())
    agent = factory.create("ideation")
    assert agent._model_config.temperature == 0.7
    assert agent._llm is None  # no key -> placeholder mode, no crash

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    factory = AgentFactory(Settings.default())
    assert factory.create("writer")._llm is not None


def test_settings_from_yaml_applies_agent_models():
    root = Path(__file__).parent.parent.parent
    settings = Settings.from_file(root / "kiwis_config.yaml")
    assert settings.agents.reviewer.model.startswith("claude")
    assert settings.agents.engineer.max_tokens == 16384
    assert "ollama" in settings.providers.providers


def test_pipeline_uses_injected_factory():
    llm = FakeLLM(JSON_REPLY)
    created = []

    def factory(role):
        from kiwis.agents import IdeationAgent
        created.append(role)
        return IdeationAgent(llm_provider=llm)

    pipe = ResearchPipeline(agent_factory=factory)
    state = PipelineState(research_topic="t")
    asyncio.run(pipe._run_hypothesis_generation(state))
    assert created == ["ideation"] and state.hypothesis == "H1"

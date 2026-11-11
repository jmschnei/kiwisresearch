"""Tests for configuration module."""

import pytest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from kiwis.config.settings import Settings
from kiwis.config.agents import AgentConfig, AgentRegistry, AgentRole
from kiwis.config.llm_providers import LLMProviderConfig, ProviderRegistry, LLMProviderType


def test_default_settings():
    settings = Settings.default()
    assert settings.project_name == "kiwis-research"
    assert settings.sandbox.mode == "docker"


def test_paths_config():
    paths = Settings().paths
    assert paths.output == Path("output")
    assert paths.data == Path("data")


def test_agent_registry_default():
    registry = AgentRegistry()
    assert hasattr(registry, "ideation")
    assert hasattr(registry, "librarian")
    assert hasattr(registry, "engineer")
    
    ideation_config = registry.get_agent(AgentRole.IDEATION)
    assert ideation_config.temperature > 0.5  # Should be high for creativity


def test_provider_registry():
    registry = ProviderRegistry()
    
    openai_cfg = LLMProviderConfig(
        provider_type=LLMProviderType.OPENAI,
        name="OpenAI",
        default_model="gpt-4o",
    )
    registry.register("openai", openai_cfg)
    
    assert len(registry.providers) == 1
    retrieved = registry.get_provider("openai")
    assert retrieved.default_model == "gpt-4o"


def test_llm_config():
    from kiwis.models.base import ModelConfig
    config = ModelConfig(model_name="test-model", temperature=0.5, max_tokens=4096)
    assert config.temperature == 0.5
    assert config.max_tokens == 4096

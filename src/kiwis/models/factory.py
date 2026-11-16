"""Factory that builds LLM provider instances from configuration."""

from __future__ import annotations

import logging
from typing import Optional

from ..config.llm_providers import LLMProviderType, ProviderRegistry
from .base import LLMProvider

logger = logging.getLogger(__name__)


def infer_provider_name(model_name: str) -> str:
    """Guess the provider name from a model name (e.g. 'claude-*' -> 'anthropic')."""
    m = model_name.lower()
    if m.startswith("ollama/"):
        return "ollama"
    if m.startswith("claude"):
        return "anthropic"
    if m.startswith("deepseek-"):
        return "deepseek"
    if m.startswith(("gpt-", "o1", "o3", "text-embedding")):
        return "openai"
    if ":" in m or m.startswith(("llama", "mistral", "phi", "gemma", "qwen", "codellama")):
        return "ollama"
    return "openai"


def create_provider(name: str, registry: ProviderRegistry) -> LLMProvider:
    """Instantiate the provider registered under ``name``. Raises on missing credentials."""
    cfg = registry.get_provider(name)
    ptype = cfg.provider_type
    if ptype == LLMProviderType.OPENAI:
        from .providers.openai_provider import OpenAIProvider
        return OpenAIProvider(base_url=cfg.base_url)
    if ptype == LLMProviderType.ANTHROPIC:
        from .providers.anthropic_provider import AnthropicProvider
        return AnthropicProvider()
    if ptype == LLMProviderType.DEEPSEEK:
        from .providers.deepseek_provider import DeepSeekProvider
        return DeepSeekProvider(base_url=cfg.base_url)
    if ptype == LLMProviderType.OLLAMA:
        from .providers.ollama_provider import OllamaProvider
        return OllamaProvider(base_url=cfg.base_url, default_model=cfg.default_model)
    raise ValueError(f"Unsupported provider type: {ptype}")


class ProviderPool:
    """Creates each provider once and caches it. Unavailable providers resolve to None."""

    def __init__(self, registry: ProviderRegistry):
        self._registry = registry
        self._cache: dict[str, Optional[LLMProvider]] = {}

    def get(self, name: str) -> Optional[LLMProvider]:
        if name not in self._cache:
            try:
                self._cache[name] = create_provider(name, self._registry)
            except Exception as e:  # missing API key, unknown provider, ...
                logger.warning(f"LLM provider '{name}' unavailable ({e}); agents using it run in placeholder mode")
                self._cache[name] = None
        return self._cache[name]

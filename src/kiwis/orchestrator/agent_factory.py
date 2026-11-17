"""Builds agents wired with their configured LLM provider and model settings."""

from __future__ import annotations

import logging
from typing import Any, Optional

from ..config.agents import AgentRole
from ..config.settings import Settings
from ..models.base import ModelConfig
from ..models.factory import ProviderPool, infer_provider_name


logger = logging.getLogger(__name__)


class AgentFactory:
    """Creates agents from ``Settings`` (per-agent model, temperature, provider)."""

    def __init__(self, settings: Optional[Settings] = None, sandbox=None, usage_tracker=None, output_dir=None):
        self._settings = settings or Settings.default()
        self._sandbox = sandbox
        self._tracker = usage_tracker
        self._output_dir = output_dir
        self._pool = ProviderPool(self._settings.providers)
        self._vector_store = None
        self._vector_store_built = False

    _BACKEND_MODULES = {"chroma": "chromadb", "qdrant": "qdrant_client", "pgvector": "asyncpg"}

    def vector_store(self):
        """Shared vector store (None if disabled or unavailable). Initialized lazily by its users."""
        if not self._vector_store_built:
            self._vector_store_built = True
            mem = self._settings.memory
            if mem.enabled:
                try:
                    from importlib.util import find_spec
                    from ..memory.factory import create_vector_store

                    module = self._BACKEND_MODULES.get(mem.vector_store.lower())
                    if module and find_spec(module) is None:
                        raise ImportError(f"'{module}' is not installed (needed for the {mem.vector_store} backend)")
                    embed_fn = self._embed_fn()
                    self._vector_store = create_vector_store(mem, embed_fn, "openai" if embed_fn else None)
                except Exception as e:
                    logger.warning(f"Vector store unavailable ({e}); literature will not be indexed")
        return self._vector_store

    def _embed_fn(self):
        """Use the OpenAI provider's embeddings when available; else Chroma's default embedder."""
        provider = self._pool.get("openai")
        return provider.embed if provider is not None else None

    def _agent_classes(self) -> dict[AgentRole, type]:
        from .. import agents as a
        return {
            AgentRole.IDEATION: a.IdeationAgent,
            AgentRole.LIBRARIAN: a.LibrarianAgent,
            AgentRole.EXPERIMENT_ARCHITECT: a.ExperimentArchitectAgent,
            AgentRole.ENGINEER: a.EngineerAgent,
            AgentRole.DATA_ANALYST: a.DataAnalystAgent,
            AgentRole.WRITER: a.WriterAgent,
            AgentRole.REVIEWER: a.ReviewerAgent,
        }

    def create(self, role: AgentRole | str) -> Any:
        role = AgentRole(role)
        cfg = self._settings.agents.get_agent(role)
        provider_name = cfg.provider or infer_provider_name(cfg.model)
        model_name = cfg.model.split("/", 1)[1] if cfg.model.lower().startswith("ollama/") else cfg.model
        provider = self._pool.get(provider_name)
        if provider is not None and self._tracker is not None:
            from ..models.usage import MeteredProvider
            provider = MeteredProvider(provider, self._tracker, agent=role.value)
        kwargs: dict[str, Any] = {
            "llm_provider": provider,
            "model_config": ModelConfig(
                model_name=model_name, temperature=cfg.temperature, max_tokens=cfg.max_tokens
            ),
        }
        if role == AgentRole.LIBRARIAN:
            kwargs["vector_store"] = self.vector_store()
        if role == AgentRole.WRITER and self._output_dir is not None:
            kwargs["output_dir"] = self._output_dir
        if role == AgentRole.ENGINEER:
            kwargs["sandbox"] = self._sandbox
        return self._agent_classes()[role](**kwargs)

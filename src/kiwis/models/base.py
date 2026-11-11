"""Abstract base for LLM provider integration."""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ModelConfig:
    """Configuration for a single model call."""
    model_name: str
    temperature: float = 0.3
    max_tokens: int = 8192
    top_p: float = 1.0
    stop_sequences: list[str] = field(default_factory=list)
    presence_penalty: float = 0.0
    frequency_penalty: float = 0.0


@dataclass
class ChatMessage:
    """Represents a single message in the conversation."""
    role: str  # "system" | "user" | "assistant"
    content: str
    name: Optional[str] = None


@abc.abstractmethod
class LLMProvider(abc.ABC):
    """Abstract interface for LLM providers."""

    @abc.abstractmethod
    async def chat(self, messages: list[ChatMessage], config: ModelConfig) -> ChatMessage:
        """Send a chat completion request and return the assistant response."""
        ...

    @abc.abstractmethod
    async def generate_text(
        self,
        prompt: str,
        system_prompt: str | None = None,
        config: Optional[ModelConfig] = None,
    ) -> str:
        """Generate text for a single-turn prompt."""
        ...

    @abc.abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embedding vectors for the given texts."""
        ...

    async def _build_messages(
        self,
        messages: list[ChatMessage],
        config: ModelConfig,
    ) -> Any:
        """Build provider-specific message format. Overridden by subclasses."""
        raise NotImplementedError


def resolve_provider_name(config: LLMProvider) -> str:
    return type(config).__name__.lower().replace("provider", "")

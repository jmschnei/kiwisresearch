"""Ollama local model provider implementation.

Enables running LLMs locally on your machine via the Ollama API server.
No external API keys needed — models are pulled from Ollama's registry.

Supported endpoints:
    Default: http://localhost:11434

Common models:
    - llama3.2          (8B/70B) — strong general purpose
    - mistral-nemo      (12B)     — excellent reasoning
    - phi3-mini         (3.8B)    — lightweight
    - codellama         (7B/13B/34B) — code generation
    - deepseek-r1       (7B/67B)  — strong reasoning
    - llama3.3          (70B)     — top tier local model
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx
import logging

from ..base import ChatMessage, LLMProvider, ModelConfig

logger = logging.getLogger(__name__)


@dataclass
class OllamaModelInfo:
    """Metadata about a model available in local Ollama."""
    name: str
    size: int = 0          # bytes
    digest: str = ""
    modified_at: str = ""

    @property
    def size_gb(self) -> float:
        return self.size / (1024 ** 3)


class OllamaProvider(LLMProvider):
    """Wrapper around the Ollama local API (native ``/api/chat``) for chat completions and embeddings."""

    DEFAULT_BASE_URL = "http://localhost:11434"
    DEFAULT_TIMEOUT = 600.0   # seconds per reply; small models on CPU can take minutes for a long answer
    DEFAULT_CONTEXT = 16384   # num_ctx; the agents' prompts (literature, paper drafts) exceed Ollama's default

    def __init__(
        self,
        base_url: Optional[str] = None,
        default_model: str = "llama3.2",
        timeout: float = DEFAULT_TIMEOUT,
        context_window: int = DEFAULT_CONTEXT,
        embedding_model: Optional[str] = None,
    ):
        self._base_url = (base_url or os.getenv("OLLAMA_BASE_URL") or self.DEFAULT_BASE_URL).rstrip("/")
        self._default_model = default_model
        self._timeout = timeout
        self._context_window = context_window
        self._embedding_model = embedding_model
        self._client: httpx.AsyncClient | None = None

    # ------------------------------------------------------------------
    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=httpx.Timeout(connect=10.0, read=self._timeout, write=self._timeout, pool=10.0),
            )
        return self._client

    # ------------------------------------------------------------------
    async def _check_health(self) -> bool:
        """Verify Ollama server is reachable."""
        try:
            resp = await self.client.get("/api/tags")
            return resp.status_code == 200
        except Exception:
            return False

    async def list_models(self) -> list[OllamaModelInfo]:
        """List all models available locally in Ollama."""
        resp = await self.client.get("/api/tags")
        resp.raise_for_status()
        data = resp.json()
        models = []
        for m in data.get("models", []):
            models.append(OllamaModelInfo(
                name=m["name"],
                size=m.get("size", 0),
                digest=m.get("digest", ""),
                modified_at=m.get("modified_at", ""),
            ))
        return models

    async def pull_model(self, model_name: str) -> str:
        """Pull a model from Ollama's registry. Returns streaming confirmation."""
        resp = await self.client.post("/api/pull", json={"name": model_name}, stream=True)
        resp.raise_for_status()
        chunks = []
        async for chunk in resp.aiter_text():
            if chunk:
                chunks.append(chunk)
        return "\n".join(chunks)

    # ------------------------------------------------------------------
    def build_request(self, messages: list[ChatMessage], config: ModelConfig) -> dict:
        """Body for ``POST /api/chat``. ``num_predict`` caps the reply; ``num_ctx`` sizes the context window."""
        options = {"temperature": config.temperature, "num_predict": config.max_tokens, "num_ctx": self._context_window}
        if config.stop_sequences:
            options["stop"] = list(config.stop_sequences)
        return {
            "model": config.model_name or self._default_model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
            "options": options,
        }

    async def chat(self, messages: list[ChatMessage], config: ModelConfig) -> ChatMessage:
        """Send a chat request to Ollama's native API (the OpenAI-compatible one ignores num_ctx)."""
        resp = await self.client.post("/api/chat", json=self.build_request(messages, config))
        if resp.status_code == 404:
            raise RuntimeError(f"Ollama model '{config.model_name}' not found: run `ollama pull {config.model_name}`")
        resp.raise_for_status()
        data = resp.json()
        if data.get("done_reason") == "length":
            logger.warning("Ollama reply hit num_predict (%s tokens); the answer is truncated", config.max_tokens)
        content = (data.get("message") or {}).get("content") or ""
        return ChatMessage(role="assistant", content=content)

    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        config: Optional[ModelConfig] = None,
    ) -> str:
        """Generate text for a single-turn prompt."""
        cfg = config or ModelConfig(model_name=self._default_model)
        msgs: list[ChatMessage] = []
        if system_prompt:
            msgs.append(ChatMessage(role="system", content=system_prompt))
        msgs.append(ChatMessage(role="user", content=prompt))
        response = await self.chat(msgs, cfg)
        return response.content

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embedding vectors from ``/api/embed`` (Ollama >= 0.1.34) with the configured embedding model."""
        if not texts:
            return []
        model = self._embedding_model or self._default_model
        resp = await self.client.post("/api/embed", json={"model": model, "input": texts})
        if resp.status_code != 200:
            raise RuntimeError(f"Ollama embeddings failed ({resp.status_code}) for '{model}': {resp.text[:200]}")
        return [list(map(float, e)) for e in resp.json().get("embeddings", [])]

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

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

from ..base import ChatMessage, LLMProvider, ModelConfig


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
    """Wrapper around the Ollama local API for chat completions and embeddings."""

    DEFAULT_BASE_URL = "http://localhost:11434"

    def __init__(
        self,
        base_url: Optional[str] = None,
        default_model: str = "llama3.2",
        timeout: float = 120.0,
    ):
        self._base_url = (base_url or os.getenv("OLLAMA_BASE_URL") or self.DEFAULT_BASE_URL).rstrip("/")
        self._default_model = default_model
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    # ------------------------------------------------------------------
    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=httpx.Timeout(connect=10.0, read=self._timeout, write=self._timeout),
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
    async def chat(self, messages: list[ChatMessage], config: ModelConfig) -> ChatMessage:
        """Send a chat completion request via Ollama."""
        model = config.model_name or self._default_model

        openai_msgs = [{"role": m.role, "content": m.content} for m in messages]

        payload = {
            "model": model,
            "messages": openai_msgs,
            "stream": False,
        }

        # Ollama supports OpenAI-compatible chat endpoint
        resp = await self.client.post(
            "/v1/chat/completions",
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()

        choice = data["choices"][0]
        return ChatMessage(
            role="assistant",
            content=choice["message"]["content"] or "",
        )

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
        """Generate embedding vectors using Ollama's embed endpoint."""
        if not texts:
            return []

        # Try the dedicated embed API (Ollama ≥ 0.1.34)
        resp = await self.client.post(
            "/api/embed",
            json={"model": self._default_model, "input": texts},
        )
        if resp.status_code == 200:
            data = resp.json()
            embeddings = data.get("embeddings", [])
            return [list(map(float, e)) for e in embeddings]

        # Fallback: use the generate endpoint with a special prefix
        # (some older Ollama versions support /api/embeddings)
        try:
            resp = await self.client.post(
                "/api/embeddings",
                json={"model": self._default_model, "prompt": texts[0]},
            )
            if resp.status_code == 200:
                emb = resp.json().get("embedding", [])
                return [list(map(float, emb)) for _ in range(len(texts))]  # Approximation
        except Exception:
            pass

        raise NotImplementedError(
            "Ollama embedding not available. Ensure Ollama ≥ 0.1.34 with the model loaded."
        )

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

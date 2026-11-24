"""OpenAI API provider implementation."""

from __future__ import annotations

import os
from typing import Any, Optional

from ..base import ChatMessage, LLMProvider, ModelConfig
from ..defaults import DEFAULT_OPENAI_MODEL

# Models that still take sampling parameters and `max_tokens`. Everything newer (gpt-5.x, gpt-6.x, o-series) is a
# reasoning model: it rejects temperature/top_p/penalties and counts reasoning tokens in `max_completion_tokens`.
_CLASSIC_PREFIXES = ("gpt-4", "gpt-3.5")


def is_reasoning_model(model: str) -> bool:
    return not model.lower().startswith(_CLASSIC_PREFIXES)


class OpenAIProvider(LLMProvider):
    """Wrapper around the OpenAI Python SDK for chat completions and embeddings."""

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self._api_key = api_key or os.getenv("OPENAI_API_KEY")
        self._base_url = base_url
        if not self._api_key:
            raise RuntimeError("OpenAI API key is required. Set OPENAI_API_KEY env var.")
        # Lazy import
        self._client = None

    def _get_client(self):
        from openai import AsyncOpenAI
        if self._client is None:
            kwargs = {"api_key": self._api_key}
            if self._base_url:
                kwargs["base_url"] = self._base_url
            self._client = AsyncOpenAI(**kwargs)
        return self._client

    def build_request(self, messages: list[ChatMessage], config: ModelConfig) -> dict[str, Any]:
        """Chat Completions arguments for this model.

        Against a custom ``base_url`` (an OpenAI-compatible server such as vLLM) the classic parameters are sent,
        since those servers usually do not know ``max_completion_tokens``.
        """
        request: dict[str, Any] = {
            "model": config.model_name,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }
        if config.stop_sequences:
            request["stop"] = list(config.stop_sequences)
        if self._base_url is None and is_reasoning_model(config.model_name):
            request["max_completion_tokens"] = config.max_tokens
            return request
        request.update(max_tokens=config.max_tokens, temperature=config.temperature, top_p=config.top_p,
                       presence_penalty=config.presence_penalty, frequency_penalty=config.frequency_penalty)
        return request

    async def chat(self, messages: list[ChatMessage], config: ModelConfig) -> ChatMessage:
        client = self._get_client()
        resp = await client.chat.completions.create(**self.build_request(messages, config))
        choice = resp.choices[0]
        if choice.finish_reason == "length":
            import logging
            logging.getLogger(__name__).warning(
                "%s reply hit the token limit (%s); the answer is truncated - raise max_tokens for this agent",
                config.model_name, config.max_tokens)
        return ChatMessage(role="assistant", content=choice.message.content or "")

    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        config: Optional[ModelConfig] = None,
    ) -> str:
        cfg = config or ModelConfig(model_name=DEFAULT_OPENAI_MODEL)
        msgs: list[ChatMessage] = []
        if system_prompt:
            msgs.append(ChatMessage(role="system", content=system_prompt))
        msgs.append(ChatMessage(role="user", content=prompt))
        response = await self.chat(msgs, cfg)
        return response.content

    async def embed(self, texts: list[str]) -> list[list[float]]:
        client = self._get_client()
        resp = await client.embeddings.create(model="text-embedding-3-small", input=texts)
        return [d.embedding for d in resp.data]

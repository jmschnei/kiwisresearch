"""OpenAI API provider implementation."""

from __future__ import annotations

import os
from typing import Any, Optional

from ..base import ChatMessage, LLMProvider, ModelConfig


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

    async def chat(self, messages: list[ChatMessage], config: ModelConfig) -> ChatMessage:
        client = self._get_client()
        openai_msgs = [{"role": m.role, "content": m.content} for m in messages]
        resp = await client.chat.completions.create(
            model=config.model_name,
            messages=openai_msgs,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            top_p=config.top_p,
            stop=config.stop_sequences if config.stop_sequences else None,
            presence_penalty=config.presence_penalty,
            frequency_penalty=config.frequency_penalty,
        )
        choice = resp.choices[0]
        return ChatMessage(role="assistant", content=choice.message.content or "")

    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        config: Optional[ModelConfig] = None,
    ) -> str:
        cfg = config or ModelConfig(model_name="gpt-4o")
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

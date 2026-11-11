"""DeepSeek provider implementation."""

from __future__ import annotations

import os
from typing import Any, Optional

from ..base import ChatMessage, LLMProvider, ModelConfig


class DeepSeekProvider(LLMProvider):
    """Wrapper around the DeepSeek API (OpenAI-compatible endpoint)."""

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self._api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        self._base_url = base_url or "https://api.deepseek.com/v1"
        if not self._api_key:
            raise RuntimeError("DeepSeek API key required. Set DEEPSEEK_API_KEY env var.")
        self._client = None

    def _get_client(self):
        from openai import AsyncOpenAI
        if self._client is None:
            self._client = AsyncOpenAI(api_key=self._api_key, base_url=self._base_url)
        return self._client

    async def chat(self, messages: list[ChatMessage], config: ModelConfig) -> ChatMessage:
        client = self._get_client()
        openai_msgs = [{"role": m.role, "content": m.content} for m in messages]
        resp = await client.chat.completions.create(
            model=config.model_name,
            messages=openai_msgs,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
        )
        choice = resp.choices[0]
        return ChatMessage(role="assistant", content=choice.message.content or "")

    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        config: Optional[ModelConfig] = None,
    ) -> str:
        cfg = config or ModelConfig(model_name="deepseek-reasoner")
        msgs: list[ChatMessage] = []
        if system_prompt:
            msgs.append(ChatMessage(role="system", content=system_prompt))
        msgs.append(ChatMessage(role="user", content=prompt))
        response = await self.chat(msgs, cfg)
        return response.content

    async def embed(self, texts: list[str]) -> list[list[float]]:
        # DeepSeek may not have embeddings; use fallback
        raise NotImplementedError("Embeddings not natively supported by DeepSeek API")

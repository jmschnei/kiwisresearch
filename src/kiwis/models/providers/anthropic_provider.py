"""Anthropic Claude provider implementation."""

from __future__ import annotations

import os
from typing import Any, Optional

from ..base import ChatMessage, LLMProvider, ModelConfig


class AnthropicProvider(LLMProvider):
    """Wrapper around the Anthropic Claude SDK for chat completions."""

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self._api_key:
            raise RuntimeError("Anthropic API key required. Set ANTHROPIC_API_KEY env var.")

    async def chat(self, messages: list[ChatMessage], config: ModelConfig) -> ChatMessage:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=self._api_key)
        system = None
        non_system_msgs: list[ChatMessage] = []
        for m in messages:
            if m.role == "system":
                system = m.content
            else:
                non_system_msgs.append(m)
        
        # Convert roles
        claude_msgs = []
        for m in non_system_msgs:
            claude_msgs.append({"role": m.role, "content": m.content})

        resp = await client.messages.create(
            model=config.model_name,
            messages=claude_msgs,
            system=system,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            top_p=config.top_p,
        )
        return ChatMessage(role="assistant", content=resp.content[0].text)

    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        config: Optional[ModelConfig] = None,
    ) -> str:
        cfg = config or ModelConfig(model_name="claude-3-5-sonnet-20241022")
        msgs: list[ChatMessage] = []
        if system_prompt:
            msgs.append(ChatMessage(role="system", content=system_prompt))
        msgs.append(ChatMessage(role="user", content=prompt))
        response = await self.chat(msgs, cfg)
        return response.content

    async def embed(self, texts: list[str]) -> list[list[float]]:
        # Claude doesn't have embeddings; use a fallback or raise
        raise NotImplementedError("Embeddings not supported by Anthropic; use text-embedding via OpenAI")

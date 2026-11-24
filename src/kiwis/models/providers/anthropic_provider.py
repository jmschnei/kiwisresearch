"""Anthropic Claude provider implementation (anthropic SDK >= 2.0, API version 2026-10-21).

Current Claude models think before answering and have fixed sampling: ``temperature`` / ``top_p`` are not sent
(the API rejects them). Requests are streamed so large ``max_tokens`` values do not hit HTTP timeouts.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

from ..base import ChatMessage, LLMProvider, ModelConfig
from ..defaults import DEFAULT_ANTHROPIC_MODEL

logger = logging.getLogger(__name__)

# Models that accept the server-side refusal fallback: if a safety classifier declines a request, the API re-runs
# it on a fallback model chosen by refusal category instead of returning an empty answer.
FALLBACK_BETA = "server-side-fallback-2026-07-01"
FALLBACK_MODELS = {"claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5", "claude-fable-5-2", "claude-fable-5-1"}


class AnthropicRefusal(RuntimeError):
    """The model (and its fallback, if any) declined the request."""


class AnthropicProvider(LLMProvider):
    """Wrapper around the Anthropic Claude SDK for chat completions."""

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self._api_key:
            raise RuntimeError("Anthropic API key required. Set ANTHROPIC_API_KEY env var.")
        self._client = None

    def _get_client(self):
        if self._client is None:
            import anthropic
            self._client = anthropic.AsyncAnthropic(api_key=self._api_key)
        return self._client

    @staticmethod
    def build_request(messages: list[ChatMessage], config: ModelConfig) -> dict[str, Any]:
        """Keyword arguments for ``messages.stream``: system prompt split out, no sampling parameters."""
        system = "\n\n".join(m.content for m in messages if m.role == "system") or None
        request: dict[str, Any] = {
            "model": config.model_name,
            "max_tokens": config.max_tokens,
            "messages": [{"role": m.role, "content": m.content} for m in messages if m.role != "system"],
        }
        if system:
            request["system"] = system
        if config.stop_sequences:
            request["stop_sequences"] = list(config.stop_sequences)
        if config.model_name in FALLBACK_MODELS:
            request["betas"] = [FALLBACK_BETA]
            request["fallbacks"] = "default"
        return request

    @staticmethod
    def response_text(message: Any) -> str:
        """Concatenated text blocks (thinking and fallback blocks are skipped). Raises on a refusal."""
        if getattr(message, "stop_reason", None) == "refusal":
            details = getattr(message, "stop_details", None)
            category = getattr(details, "category", None) if details else None
            raise AnthropicRefusal(f"Claude declined the request (category: {category or 'unspecified'})")
        if getattr(message, "stop_reason", None) == "max_tokens":
            logger.warning("Claude reply hit max_tokens (%s); the answer is truncated - raise max_tokens for this agent",
                           getattr(getattr(message, "usage", None), "output_tokens", "?"))
        return "".join(block.text for block in message.content if getattr(block, "type", None) == "text")

    async def chat(self, messages: list[ChatMessage], config: ModelConfig) -> ChatMessage:
        client = self._get_client()
        request = self.build_request(messages, config)
        api = client.beta.messages if "betas" in request else client.messages
        async with api.stream(**request) as stream:
            message = await stream.get_final_message()
        return ChatMessage(role="assistant", content=self.response_text(message))

    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        config: Optional[ModelConfig] = None,
    ) -> str:
        cfg = config or ModelConfig(model_name=DEFAULT_ANTHROPIC_MODEL)
        msgs: list[ChatMessage] = []
        if system_prompt:
            msgs.append(ChatMessage(role="system", content=system_prompt))
        msgs.append(ChatMessage(role="user", content=prompt))
        response = await self.chat(msgs, cfg)
        return response.content

    async def embed(self, texts: list[str]) -> list[list[float]]:
        # Claude doesn't have embeddings; use a fallback or raise
        raise NotImplementedError("Embeddings not supported by Anthropic; use text-embedding via OpenAI")

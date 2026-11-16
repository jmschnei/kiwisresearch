"""Token/cost accounting for LLM calls.

Providers don't report real usage through the ``LLMProvider`` interface, so token counts
are estimates (~4 characters per token). Prices are approximate USD per 1M tokens and can be
overridden through ``UsageTracker(prices=...)``.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Optional

from .base import ChatMessage, LLMProvider, ModelConfig

# (input, output) USD per 1M tokens; matched by model-name prefix, longest prefix first.
DEFAULT_PRICES: dict[str, tuple[float, float]] = {
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "gpt-4-turbo": (10.00, 30.00),
    "claude-3-5-sonnet": (3.00, 15.00),
    "claude-3-opus": (15.00, 75.00),
    "deepseek": (0.27, 1.10),
}


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4) if text else 0


@dataclass
class UsageRecord:
    agent: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    timestamp: float = field(default_factory=time.time)

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


class UsageTracker:
    """Collects usage records for one pipeline run."""

    def __init__(
        self,
        prices: Optional[dict[str, tuple[float, float]]] = None,
        on_record: Optional[Callable[[UsageRecord], None]] = None,
    ):
        self._prices = prices or DEFAULT_PRICES
        self._on_record = on_record
        self.records: list[UsageRecord] = []

    def cost_for(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        for prefix in sorted(self._prices, key=len, reverse=True):
            if model.lower().startswith(prefix):
                p_in, p_out = self._prices[prefix]
                return (prompt_tokens * p_in + completion_tokens * p_out) / 1_000_000
        return 0.0  # unknown / local models (e.g. Ollama) are free

    def record(self, agent: str, model: str, prompt_tokens: int, completion_tokens: int) -> UsageRecord:
        rec = UsageRecord(agent, model, prompt_tokens, completion_tokens,
                          self.cost_for(model, prompt_tokens, completion_tokens))
        self.records.append(rec)
        if self._on_record:
            self._on_record(rec)
        return rec

    @property
    def total_tokens(self) -> int:
        return sum(r.total_tokens for r in self.records)

    @property
    def total_cost(self) -> float:
        return sum(r.cost_usd for r in self.records)

    def by_agent(self) -> dict[str, dict]:
        out: dict[str, dict] = {}
        for r in self.records:
            a = out.setdefault(r.agent, {"tokens": 0, "costUsd": 0.0})
            a["tokens"] += r.total_tokens
            a["costUsd"] += r.cost_usd
        return out


class MeteredProvider(LLMProvider):
    """Wraps a provider and records (estimated) usage per agent."""

    def __init__(self, inner: LLMProvider, tracker: UsageTracker, agent: str):
        self._inner = inner
        self._tracker = tracker
        self._agent = agent

    async def chat(self, messages: list[ChatMessage], config: ModelConfig) -> ChatMessage:
        reply = await self._inner.chat(messages, config)
        self._tracker.record(
            self._agent,
            config.model_name,
            sum(estimate_tokens(m.content) for m in messages),
            estimate_tokens(reply.content),
        )
        return reply

    async def generate_text(self, prompt, system_prompt=None, config=None) -> str:
        text = await self._inner.generate_text(prompt, system_prompt, config)
        model = config.model_name if config else "unknown"
        self._tracker.record(
            self._agent, model,
            estimate_tokens(prompt) + estimate_tokens(system_prompt or ""), estimate_tokens(text),
        )
        return text

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return await self._inner.embed(texts)

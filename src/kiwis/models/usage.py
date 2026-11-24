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
    # OpenAI (gpt-4o family shuts down 2027-01-14)
    "gpt-6.2-astra": (8.00, 40.00),
    "gpt-6.2-sol": (2.00, 10.00),
    "gpt-6.1-terra": (1.00, 5.00),
    "gpt-6-luna": (0.10, 0.50),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    # Anthropic
    "claude-opus-5-5": (4.00, 20.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-haiku-5-5": (0.10, 0.50),
    # DeepSeek (peak-hour list prices; off-peak is half)
    "deepseek-v4-pro": (1.32, 3.96),
    "deepseek-flash": (0.30, 1.20),
    "deepseek": (0.30, 1.20),
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

    def __init__(self, inner: LLMProvider, tracker: Optional[UsageTracker], agent: str, transcript_dir=None):
        self._inner = inner
        self._tracker = tracker
        self._agent = agent
        self._transcript_dir = transcript_dir

    def _record(self, model: str, prompt_tokens: int, completion_tokens: int) -> None:
        if self._tracker is not None:
            self._tracker.record(self._agent, model, prompt_tokens, completion_tokens)

    def _write_transcript(self, messages: list[ChatMessage], config: ModelConfig, reply: str, seconds: float) -> None:
        """``<transcript_dir>/NN-<agent>.md``: the exact prompt and the raw reply, to see what the model really did."""
        if self._transcript_dir is None:
            return
        from pathlib import Path
        try:
            folder = Path(self._transcript_dir)
            folder.mkdir(parents=True, exist_ok=True)
            n = len(list(folder.glob("*.md"))) + 1
            parts = [f"# {self._agent} - {config.model_name} ({seconds:.1f}s)\n"]
            parts += [f"## {m.role}\n\n{m.content}\n" for m in messages]
            parts.append(f"## reply\n\n{reply}\n")
            (folder / f"{n:02d}-{self._agent}.md").write_text("\n".join(parts))
        except OSError:
            pass  # a transcript must never break the run

    async def chat(self, messages: list[ChatMessage], config: ModelConfig) -> ChatMessage:
        started = time.monotonic()
        reply = await self._inner.chat(messages, config)
        self._record(config.model_name, sum(estimate_tokens(m.content) for m in messages), estimate_tokens(reply.content))
        self._write_transcript(messages, config, reply.content, time.monotonic() - started)
        return reply

    async def generate_text(self, prompt, system_prompt=None, config=None) -> str:
        text = await self._inner.generate_text(prompt, system_prompt, config)
        model = config.model_name if config else "unknown"
        self._record(model, estimate_tokens(prompt) + estimate_tokens(system_prompt or ""), estimate_tokens(text))
        return text

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return await self._inner.embed(texts)

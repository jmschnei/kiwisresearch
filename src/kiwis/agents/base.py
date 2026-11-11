"""Base class for all research agents."""

from __future__ import annotations

import json
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class AgentState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRY = "retry"


@dataclass
class AgentOutput:
    """Standardized output from any agent."""
    agent_name: str
    state: AgentState
    data: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "agent_name": self.agent_name,
            "state": self.state.value,
            "data": self.data,
            "metadata": self.metadata,
            "error": self.error,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


@dataclass
class AgentContext:
    """Shared context passed between agents via the bus."""
    research_topic: str = ""
    hypothesis: str = ""
    literature_review: dict = field(default_factory=dict)
    experiment_plan: dict = field(default_factory=dict)
    execution_results: dict[str, Any] = field(default_factory=dict)
    analysis: dict = field(default_factory=dict)
    paper_draft: dict = field(default_factory=dict)
    review_feedback: list[dict] = field(default_factory=list)
    artifacts: dict[str, str] = field(default_factory=dict)  # name -> path

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}

    @classmethod
    def from_dict(cls, d: dict) -> AgentContext:
        return cls(**d)


class BaseAgent(ABC):
    """Abstract base class for research agents."""

    ROLE: str = ""
    DESCRIPTION: str = ""

    def __init__(self, name: Optional[str] = None):
        self.name = name or f"{self.ROLE}-agent"
        self.state = AgentState.PENDING
        self.output: Optional[AgentOutput] = None

    @abstractmethod
    async def execute(self, context: AgentContext) -> AgentOutput:
        """Main execution method for the agent."""
        ...

    def _get_system_prompt(self) -> str:
        """Default system prompt. Override in subclasses."""
        return f"You are a specialized {self.ROLE} agent in the Kiwis Research system.\n{self.DESCRIPTION}"

    def _log_event(self, event: str, details: dict | None = None):
        """Log agent events (use logger in production)."""
        meta = details or {}
        pass  # TODO: integrate with loguru

    @classmethod
    def get_role(cls) -> str:
        return cls.ROLE

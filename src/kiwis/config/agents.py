"""Agent-specific configuration."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class AgentRole(str, Enum):
    IDEATION = "ideation"
    LIBRARIAN = "librarian"
    EXPERIMENT_ARCHITECT = "experiment_architect"
    ENGINEER = "engineer"
    DATA_ANALYST = "data_analyst"
    WRITER = "writer"
    REVIEWER = "reviewer"


class AgentConfig(BaseModel):
    """Configuration for a single agent."""
    role: AgentRole
    model: str = Field(default="gpt-4o")
    provider: str = Field(default="openai")
    temperature: float = Field(default=0.3, ge=0.0, le=2.0)
    system_prompt_path: Optional[str] = None
    max_tokens: int = Field(default=8192, ge=256)
    enabled: bool = Field(default=True)


class AgentRegistry(BaseModel):
    """Registry of all agents in the system."""
    ideation: AgentConfig = Field(
        default_factory=lambda: AgentConfig(role=AgentRole.IDEATION, temperature=0.7)
    )
    librarian: AgentConfig = Field(
        default_factory=lambda: AgentConfig(role=AgentRole.LIBRARIAN, temperature=0.2)
    )
    experiment_architect: AgentConfig = Field(
        default_factory=lambda: AgentConfig(role=AgentRole.EXPERIMENT_ARCHITECT, temperature=0.4)
    )
    engineer: AgentConfig = Field(
        default_factory=lambda: AgentConfig(role=AgentRole.ENGINEER, temperature=0.2)
    )
    data_analyst: AgentConfig = Field(
        default_factory=lambda: AgentConfig(role=AgentRole.DATA_ANALYST, temperature=0.3)
    )
    writer: AgentConfig = Field(
        default_factory=lambda: AgentConfig(role=AgentRole.WRITER, temperature=0.4)
    )
    reviewer: AgentConfig = Field(
        default_factory=lambda: AgentConfig(role=AgentRole.REVIEWER, temperature=0.1)
    )

    def get_agent(self, role: AgentRole) -> AgentConfig:
        return getattr(self, role.value)

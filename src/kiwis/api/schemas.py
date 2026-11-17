"""Request DTOs (field names match the dashboard's camelCase types)."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class CreateResearchRequest(BaseModel):
    title: str = Field(min_length=1)
    type: str = "paper"
    domain: str = "ml"
    hypothesis: str = ""
    agentIds: list[str] = Field(default_factory=list)
    model: Optional[str] = None
    maxTokensPerIteration: Optional[int] = None
    budgetUsd: float = 0.0  # 0 = no budget limit
    depthLevel: Literal["fast", "standard", "deep", "max"] = "standard"


class UpdatePipelineStatusRequest(BaseModel):
    pipelineId: Optional[str] = None
    status: Literal["active", "paused", "completed", "failed"]
    reason: Optional[str] = None


class ReexecuteStepRequest(BaseModel):
    pipelineId: str
    stepNum: int
    cascade: bool = False  # also run every step after stepNum ("continue from here")
    override: Optional[dict[str, Any]] = None


class CleanupRequest(BaseModel):
    olderThanDays: Optional[int] = Field(default=None, ge=0)
    keepLast: Optional[int] = Field(default=None, ge=0)
    dryRun: bool = False

"""Global application settings."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field


class PathsConfig(BaseModel):
    """Directory layout for the research project."""
    output: Path = Field(default=Path("output"))
    data: Path = Field(default=Path("data"))
    experiments: Path = Field(default=Path("data", "experiments"))
    artifacts: Path = Field(default=Path("output", "artifacts"))
    papers_dir: Path = Field(default=Path("output", "papers"))
    sandbox_workspace: Path = Field(default=Path("/tmp/kiwis_sandbox"))


class ResearchPipelineConfig(BaseModel):
    """Controls the research pipeline flow."""
    max_iterations: int = Field(default=10, ge=1)
    hypothesis_generation_rounds: int = Field(default=3, ge=1)
    literature_review_papers_max: int = Field(default=20, ge=5)
    peer_review_critique_rounds: int = Field(default=2, ge=1)
    auto_submit_threshold: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    max_paper_length: int = Field(default=8, ge=1)  # pages


class SandboxConfig(BaseModel):
    """Sandbox execution environment settings."""
    mode: str = Field(default="docker")  # docker | isolated
    timeout_seconds: int = Field(default=600, ge=10)
    memory_mb: int = Field(default=4096, ge=512)
    network_isolated: bool = Field(default=True)
    gpu_available: bool = Field(default=False)


class LoggingConfig(BaseModel):
    """Logging configuration."""
    level: str = Field(default="INFO")
    format: str = Field(default="%(asctime)s | %(name)s | %(levelname)-8s | %(message)s")
    file: Optional[Path] = Field(default=Path("output", "kiwis.log"))


class Settings(BaseModel):
    """Top-level settings for the Kiwis Research system."""
    project_name: str = Field(default="kiwis-research")
    paths: PathsConfig = Field(default_factory=PathsConfig)
    pipeline: ResearchPipelineConfig = Field(default_factory=ResearchPipelineConfig)
    sandbox: SandboxConfig = Field(default_factory=SandboxConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    # LLM defaults (can be overridden per-agent)
    default_provider: str = Field(default="openai")
    default_model: str = Field(default="gpt-4o")
    
    @classmethod
    def from_file(cls, path: Path | str) -> Settings:
        p = Path(path) if isinstance(path, str) else path
        with open(p) as f:
            data = yaml.safe_load(f)
        return cls(**data)

    @classmethod
    def default(cls) -> Settings:
        return cls()

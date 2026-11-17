"""Global application settings."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field, model_validator

from .agents import AgentRegistry
from .llm_providers import ProviderRegistry


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


class MemoryConfig(BaseModel):
    """Vector store settings."""
    enabled: bool = Field(default=True)
    vector_store: str = Field(default="chroma")  # chroma | qdrant | pgvector
    persist_dir: str = Field(default="./chroma_kiwis")  # chroma data; qdrant local mode uses <persist_dir>/qdrant
    collection: str = Field(default="kiwis_papers")  # an embedder tag is appended (e.g. kiwis_papers_openai)
    url: Optional[str] = Field(default=None)  # qdrant server URL or pgvector DSN (or env KIWIS_VECTOR_URL)


class RetentionConfig(BaseModel):
    """Automatic cleanup of finished research jobs (output/jobs). Disabled unless a limit is set.

    Only completed or failed jobs are ever removed, oldest first; running and paused jobs are never touched.
    """
    max_age_days: Optional[int] = Field(default=None, ge=1)  # delete finished jobs older than this
    max_jobs: Optional[int] = Field(default=None, ge=1)      # keep at most this many finished jobs (newest)


class Settings(BaseModel):
    """Top-level settings for the Kiwis Research system."""
    project_name: str = Field(default="kiwis-research")
    paths: PathsConfig = Field(default_factory=PathsConfig)
    pipeline: ResearchPipelineConfig = Field(default_factory=ResearchPipelineConfig)
    sandbox: SandboxConfig = Field(default_factory=SandboxConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    retention: RetentionConfig = Field(default_factory=RetentionConfig)

    # LLM defaults (can be overridden per-agent)
    default_provider: str = Field(default="openai")
    default_model: str = Field(default="gpt-4o")

    # Per-agent model settings and LLM provider registry
    agents: AgentRegistry = Field(default_factory=AgentRegistry)
    providers: ProviderRegistry = Field(default_factory=ProviderRegistry.with_defaults)

    @model_validator(mode="before")
    @classmethod
    def _normalize_yaml(cls, data):
        """Accept the YAML layout: agents without explicit role, partial provider overrides."""
        if not isinstance(data, dict):
            return data
        data = dict(data)
        agents = data.get("agents")
        if isinstance(agents, dict):
            data["agents"] = {
                key: {"role": key, **cfg} if isinstance(cfg, dict) else cfg
                for key, cfg in agents.items()
            }
        providers = data.get("providers")
        if isinstance(providers, dict) and "providers" not in providers:
            merged = {
                name: cfg.model_dump() for name, cfg in ProviderRegistry.with_defaults().providers.items()
            }
            for name, cfg in providers.items():
                base = merged.get(name, {"name": name})
                merged[name] = {**base, **(cfg or {})}
            data["providers"] = {"providers": merged}
        # Optional [ollama] block overrides the Ollama provider endpoint/model
        ollama = data.get("ollama")
        if isinstance(ollama, dict) and ollama.get("enabled"):
            prov = data.setdefault("providers", {})
            if "providers" not in prov:
                prov = data["providers"] = {
                    "providers": {n: c.model_dump() for n, c in ProviderRegistry.with_defaults().providers.items()}
                }
            o = prov["providers"].setdefault("ollama", {"name": "Ollama (local)", "provider_type": "ollama"})
            if ollama.get("base_url"):
                o["base_url"] = ollama["base_url"]
            if ollama.get("default_model"):
                o["default_model"] = ollama["default_model"]
        return data
    
    @classmethod
    def from_file(cls, path: Path | str) -> Settings:
        p = Path(path) if isinstance(path, str) else path
        with open(p) as f:
            data = yaml.safe_load(f)
        return cls(**data)

    @classmethod
    def default(cls) -> Settings:
        return cls()


def load_settings(path: Path | str | None = None) -> Settings:
    """Load settings from a YAML file, or return defaults when no path is given."""
    return Settings.from_file(path) if path else Settings.default()

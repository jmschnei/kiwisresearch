"""LLM provider configuration."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class LLMProviderType(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    DEEPSEEK = "deepseek"
    AZURE = "azure"


class APIKeySource(str, Enum):
    ENV = "env"
    VAULT = "vault"
    FILE = "file"
    MANAGED = "managed"


class LLMProviderConfig(BaseModel):
    """Configuration for one LLM provider."""
    provider_type: LLMProviderType
    name: str
    api_key_env_var: Optional[str] = None
    base_url: Optional[str] = None
    default_model: str = "gpt-4o"
    supported_models: list[str] = Field(default_factory=list)
    rate_limit_rpm: int = Field(default=1000, ge=1)
    rate_limit_tpd: int = Field(default=500000, ge=1)


class ProviderRegistry(BaseModel):
    """Registry of available LLM providers."""
    providers: dict[str, LLMProviderConfig] = Field(default_factory=dict)
    default: str = "openai"

    def register(self, name: str, config: LLMProviderConfig) -> None:
        self.providers[name] = config

    def get_default(self) -> LLMProviderConfig:
        if self.default in self.providers:
            return self.providers[self.default]
        raise KeyError(f"Default provider '{self.default}' not found")

    def get_provider(self, name: str) -> LLMProviderConfig:
        if name not in self.providers:
            raise KeyError(f"Provider '{name}' not registered")
        return self.providers[name]

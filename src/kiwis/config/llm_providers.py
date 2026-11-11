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
    OLLAMA = "ollama"


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

    @classmethod
    def with_defaults(cls) -> "ProviderRegistry":
        """Create a registry pre-loaded with the recommended default providers."""
        reg = cls(default="openai")
        reg.register(
            "openai",
            LLMProviderConfig(
                provider_type=LLMProviderType.OPENAI,
                name="OpenAI",
                api_key_env_var="OPENAI_API_KEY",
                base_url=None,
                default_model="gpt-4o",
                supported_models=["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"],
            ),
        )
        reg.register(
            "anthropic",
            LLMProviderConfig(
                provider_type=LLMProviderType.ANTHROPIC,
                name="Anthropic Claude",
                api_key_env_var="ANTHROPIC_API_KEY",
                default_model="claude-3-5-sonnet-20241022",
                supported_models=["claude-3-5-sonnet-20241022", "claude-3-opus-20240229"],
            ),
        )
        reg.register(
            "deepseek",
            LLMProviderConfig(
                provider_type=LLMProviderType.DEEPSEEK,
                name="DeepSeek",
                api_key_env_var="DEEPSEEK_API_KEY",
                base_url="https://api.deepseek.com/v1",
                default_model="deepseek-reasoner",
                supported_models=["deepseek-reasoner", "deepseek-chat"],
            ),
        )
        reg.register(
            "ollama",
            LLMProviderConfig(
                provider_type=LLMProviderType.OLLAMA,
                name="Ollama (local)",
                api_key_env_var=None,  # No API key needed for local Ollama
                base_url="http://localhost:11434",
                default_model="llama3.2",
                supported_models=[
                    "llama3.2",
                    "llama3.2:1b",
                    "llama3.2:3b",
                    "llama3.2:11b",
                    "llama3.2:90b",
                    "llama3.3",
                    "llama3.3:70b",
                    "mistral-nemo",
                    "phi3-mini",
                    "codellama",
                    "deepseek-r1",
                    "deepseek-r1:671b",
                ],
            ),
        )
        return reg

    @property
    def available_models(self) -> dict[str, list[str]]:
        """Get all models grouped by provider name."""
        return {name: cfg.supported_models for name, cfg in self.providers.items()}

    @classmethod
    def from_yaml(cls, path: str) -> "ProviderRegistry":
        import yaml
        with open(path) as f:
            data = yaml.safe_load(f)
        
        reg = cls(default=data.get("default", "openai"))
        for name, cfg in data.get("providers", {}).items():
            if name == "default":
                continue
            reg.register(
                name,
                LLMProviderConfig(
                    provider_type=LLMProviderType(cfg.get("provider_type", "openai")),
                    name=cfg.get("name", name),
                    api_key_env_var=cfg.get("api_key_env_var"),
                    base_url=cfg.get("base_url"),
                    default_model=cfg.get("default_model", "gpt-4o"),
                    supported_models=cfg.get("supported_models", []),
                ),
            )
        return reg

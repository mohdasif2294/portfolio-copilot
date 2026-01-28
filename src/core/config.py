"""Configuration management for LLM providers."""

import os
from dataclasses import dataclass, field
from typing import Literal

from dotenv import load_dotenv

load_dotenv()

ProviderType = Literal["ollama", "claude"]


@dataclass
class LLMConfig:
    """Configuration for LLM providers."""

    provider: ProviderType = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3"
    claude_model: str = "claude-sonnet-4-20250514"

    @classmethod
    def from_env(cls) -> "LLMConfig":
        """Load configuration from environment variables."""
        provider = os.getenv("LLM_PROVIDER", "ollama").lower()
        if provider not in ("ollama", "claude"):
            provider = "ollama"

        return cls(
            provider=provider,  # type: ignore
            ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            ollama_model=os.getenv("OLLAMA_MODEL", "llama3"),
            claude_model=os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514"),
        )


# Global config instance (singleton pattern)
_config: LLMConfig | None = None


def get_config() -> LLMConfig:
    """Get the current LLM configuration.

    Returns a singleton instance, loading from environment on first call.
    """
    global _config
    if _config is None:
        _config = LLMConfig.from_env()
    return _config


def set_provider(
    provider: ProviderType,
    model: str | None = None,
) -> None:
    """Override the current provider configuration.

    Used by CLI to set provider from command-line arguments.

    Args:
        provider: The provider to use ("ollama" or "claude")
        model: Optional model name override
    """
    global _config
    config = get_config()

    # Create a new config with updated values
    _config = LLMConfig(
        provider=provider,
        ollama_base_url=config.ollama_base_url,
        ollama_model=model if model and provider == "ollama" else config.ollama_model,
        claude_model=model if model and provider == "claude" else config.claude_model,
    )


def reset_config() -> None:
    """Reset configuration to reload from environment.

    Useful for testing.
    """
    global _config
    _config = None

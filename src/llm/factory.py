"""Factory functions for creating LLM providers."""

from src.core.config import get_config
from src.llm.base import LLMProvider, SimpleProvider


def get_llm_provider() -> LLMProvider:
    """Get an LLM provider based on current configuration.

    Returns:
        LLMProvider instance (either Claude or Ollama)
    """
    config = get_config()

    if config.provider == "claude":
        from src.llm.claude import ClaudeProvider

        return ClaudeProvider(model=config.claude_model)
    else:
        from src.llm.ollama import OllamaProvider

        return OllamaProvider(
            base_url=config.ollama_base_url,
            model=config.ollama_model,
        )


def get_simple_provider() -> SimpleProvider:
    """Get a simple LLM provider for basic completions.

    Used by workflow nodes that don't need tool calling.

    Returns:
        SimpleProvider instance (either Claude or Ollama)
    """
    config = get_config()

    if config.provider == "claude":
        from src.llm.claude import ClaudeSimpleProvider

        return ClaudeSimpleProvider(model=config.claude_model)
    else:
        from src.llm.ollama import OllamaSimpleProvider

        return OllamaSimpleProvider(
            base_url=config.ollama_base_url,
            model=config.ollama_model,
        )

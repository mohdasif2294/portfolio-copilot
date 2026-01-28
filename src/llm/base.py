"""Base protocol definitions for LLM providers."""

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class ToolCall:
    """A tool call from an LLM."""

    id: str
    name: str
    input: dict[str, Any]


@dataclass
class CompletionResponse:
    """Response from an LLM completion request."""

    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    stop_reason: str = "end_turn"


@dataclass
class StreamEvent:
    """An event from a streaming response."""

    type: str  # "text", "tool_use", "done"
    text: str = ""
    tool_call: ToolCall | None = None


class LLMProvider(Protocol):
    """Protocol for full-featured LLM providers with tool support."""

    async def complete(
        self,
        messages: list[dict[str, Any]],
        system: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int = 4096,
    ) -> CompletionResponse:
        """Generate a completion with optional tool calling.

        Args:
            messages: Conversation messages in provider-agnostic format
            system: Optional system prompt
            tools: Optional list of tool definitions
            max_tokens: Maximum tokens to generate

        Returns:
            CompletionResponse with content and any tool calls
        """
        ...

    async def stream(
        self,
        messages: list[dict[str, Any]],
        system: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int = 4096,
    ) -> AsyncIterator[StreamEvent]:
        """Stream a completion response.

        Args:
            messages: Conversation messages in provider-agnostic format
            system: Optional system prompt
            tools: Optional list of tool definitions
            max_tokens: Maximum tokens to generate

        Yields:
            StreamEvent objects as the response is generated
        """
        ...


class SimpleProvider(Protocol):
    """Protocol for simple completion-only LLM providers.

    Used by workflow nodes that don't need tool calling.
    """

    async def complete(
        self,
        messages: list[dict[str, Any]],
        system: str | None = None,
        max_tokens: int = 1024,
    ) -> str:
        """Generate a simple text completion.

        Args:
            messages: Conversation messages
            system: Optional system prompt
            max_tokens: Maximum tokens to generate

        Returns:
            Generated text content
        """
        ...

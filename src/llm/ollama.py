"""Ollama LLM provider implementation."""

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from src.core.config import get_config
from src.llm.base import CompletionResponse, StreamEvent, ToolCall
from src.llm.tool_parser import format_tools_as_prompt, parse_tool_calls_from_text


class OllamaProvider:
    """Full-featured Ollama provider with prompt-based tool calling."""

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float = 120.0,
    ):
        """Initialize Ollama provider.

        Args:
            base_url: Ollama API base URL (defaults to config)
            model: Model name (defaults to config)
            timeout: Request timeout in seconds
        """
        config = get_config()
        self._base_url = (base_url or config.ollama_base_url).rstrip("/")
        self._model = model or config.ollama_model
        self._timeout = timeout
        self._client = httpx.AsyncClient(timeout=timeout)

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    async def __aenter__(self) -> "OllamaProvider":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    def _build_messages(
        self,
        messages: list[dict[str, Any]],
        system: str | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, str]]:
        """Build Ollama-formatted messages with tool instructions.

        Args:
            messages: Input messages
            system: System prompt
            tools: Tool definitions

        Returns:
            Ollama-formatted messages
        """
        ollama_messages: list[dict[str, str]] = []

        # Build system message with tool instructions
        system_parts = []
        if system:
            system_parts.append(system)
        if tools:
            system_parts.append(format_tools_as_prompt(tools))

        if system_parts:
            ollama_messages.append({
                "role": "system",
                "content": "\n\n".join(system_parts),
            })

        # Convert messages
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            # Handle Claude-style content arrays
            if isinstance(content, list):
                text_parts = []
                for block in content:
                    if isinstance(block, dict):
                        if block.get("type") == "text":
                            text_parts.append(block.get("text", ""))
                        elif block.get("type") == "tool_result":
                            # Format tool result as pretty-printed JSON
                            result = block.get("content")
                            if result is None:
                                result_json = ""
                            else:
                                result_json = json.dumps(result, ensure_ascii=False, indent=2)
                            tool_id = block.get("tool_use_id", "unknown")
                            text_parts.append(
                                f"Tool result ({tool_id}):\n```json\n{result_json}\n```"
                            )
                    else:
                        text_parts.append(str(block))
                content = "\n".join(text_parts)

            ollama_messages.append({
                "role": role if role in ("user", "assistant", "system") else "user",
                "content": content,
            })

        return ollama_messages

    async def complete(
        self,
        messages: list[dict[str, Any]],
        system: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int = 4096,
    ) -> CompletionResponse:
        """Generate a completion with optional tool calling.

        Args:
            messages: Conversation messages
            system: Optional system prompt
            tools: Optional tool definitions
            max_tokens: Maximum tokens to generate

        Returns:
            CompletionResponse with content and any tool calls
        """
        ollama_messages = self._build_messages(messages, system, tools)

        payload = {
            "model": self._model,
            "messages": ollama_messages,
            "stream": False,
            "options": {
                "num_predict": max_tokens,
            },
        }

        try:
            response = await self._client.post(
                f"{self._base_url}/api/chat",
                json=payload,
            )
            response.raise_for_status()
        except httpx.ConnectError as e:
            raise ConnectionError(
                f"Cannot connect to Ollama at {self._base_url}. "
                f"Make sure Ollama is running ('ollama serve') or use --provider claude."
            ) from e
        except httpx.HTTPStatusError as e:
            raise ConnectionError(
                f"Ollama request failed: {e.response.status_code}. "
                f"Make sure model '{self._model}' is available ('ollama pull {self._model}')."
            ) from e

        data = response.json()
        content = data.get("message", {}).get("content", "")

        # Parse tool calls from response
        remaining_text, tool_calls = parse_tool_calls_from_text(content, tools)

        # If tool calls were found, discard remaining text (likely hallucinated results)
        # The model tends to output tool calls then immediately hallucinate responses
        if tool_calls:
            remaining_text = ""
            stop_reason = "tool_use"
        else:
            stop_reason = "end_turn"

        return CompletionResponse(
            content=remaining_text,
            tool_calls=tool_calls,
            stop_reason=stop_reason,
        )

    async def stream(
        self,
        messages: list[dict[str, Any]],
        system: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int = 4096,
    ) -> AsyncIterator[StreamEvent]:
        """Stream a completion response.

        For tool-enabled requests, uses non-streaming to prevent hallucination.
        The model tends to output tool calls and then immediately hallucinate
        results instead of waiting, so we need to intercept after the first
        complete tool call.

        Args:
            messages: Conversation messages
            system: Optional system prompt
            tools: Optional tool definitions
            max_tokens: Maximum tokens to generate

        Yields:
            StreamEvent objects as the response is generated
        """
        # For tool-enabled requests, use non-streaming to prevent hallucination
        if tools:
            response = await self.complete(messages, system, tools, max_tokens)

            if response.content:
                yield StreamEvent(type="text", text=response.content)

            for tc in response.tool_calls:
                yield StreamEvent(type="tool_use", tool_call=tc)

            yield StreamEvent(type="done")
            return

        # For non-tool requests, use streaming
        ollama_messages = self._build_messages(messages, system, None)

        payload = {
            "model": self._model,
            "messages": ollama_messages,
            "stream": True,
            "options": {
                "num_predict": max_tokens,
            },
        }

        try:
            async with self._client.stream(
                "POST",
                f"{self._base_url}/api/chat",
                json=payload,
            ) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if not line:
                        continue

                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    message = data.get("message", {})
                    content = message.get("content", "")

                    if content:
                        yield StreamEvent(type="text", text=content)

                    if data.get("done", False):
                        yield StreamEvent(type="done")
                        break
        except httpx.ConnectError as e:
            raise ConnectionError(
                f"Cannot connect to Ollama at {self._base_url}. "
                f"Make sure Ollama is running ('ollama serve') or use --provider claude."
            ) from e
        except httpx.HTTPStatusError as e:
            raise ConnectionError(
                f"Ollama request failed: {e.response.status_code}. "
                f"Make sure model '{self._model}' is available ('ollama pull {self._model}')."
            ) from e


class OllamaSimpleProvider:
    """Simple Ollama provider for basic completions without tool calling."""

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float = 120.0,
    ):
        """Initialize simple Ollama provider.

        Args:
            base_url: Ollama API base URL (defaults to config)
            model: Model name (defaults to config)
            timeout: Request timeout in seconds
        """
        config = get_config()
        self._base_url = (base_url or config.ollama_base_url).rstrip("/")
        self._model = model or config.ollama_model
        self._timeout = timeout
        self._client = httpx.AsyncClient(timeout=timeout)

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

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
        ollama_messages: list[dict[str, str]] = []

        if system:
            ollama_messages.append({"role": "system", "content": system})

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            # Handle content that's a list (Claude format)
            if isinstance(content, list):
                text_parts = []
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text_parts.append(block.get("text", ""))
                    elif isinstance(block, str):
                        text_parts.append(block)
                content = "\n".join(text_parts)

            ollama_messages.append({
                "role": role if role in ("user", "assistant", "system") else "user",
                "content": content,
            })

        payload = {
            "model": self._model,
            "messages": ollama_messages,
            "stream": False,
            "options": {
                "num_predict": max_tokens,
            },
        }

        try:
            response = await self._client.post(
                f"{self._base_url}/api/chat",
                json=payload,
            )
            response.raise_for_status()
        except httpx.ConnectError as e:
            raise ConnectionError(
                f"Cannot connect to Ollama at {self._base_url}. "
                f"Make sure Ollama is running ('ollama serve') or use --provider claude."
            ) from e
        except httpx.HTTPStatusError as e:
            raise ConnectionError(
                f"Ollama request failed: {e.response.status_code}. "
                f"Make sure model '{self._model}' is available ('ollama pull {self._model}')."
            ) from e

        data = response.json()
        return data.get("message", {}).get("content", "")

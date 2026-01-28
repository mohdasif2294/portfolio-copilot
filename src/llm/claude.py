"""Claude client with streaming and tool support."""

import json
import os
from collections.abc import AsyncIterator
from typing import Any

from anthropic import Anthropic, AsyncAnthropic
from dotenv import load_dotenv

from src.core.config import get_config
from src.llm.base import CompletionResponse, StreamEvent, ToolCall
from src.llm.tools import get_all_tools
from src.mcp.kite_client import KiteClient

load_dotenv()

MAX_TOKENS = 4096

SYSTEM_PROMPT = """You are Portfolio Copilot, an AI assistant that helps users understand and analyze their stock portfolio on Zerodha Kite.

You have access to:
1. The user's Kite account through portfolio tools (holdings, positions, margins, quotes)
2. A news database through RAG tools (search_news, ingest_stock_news)

Guidelines:
- Always fetch fresh data using tools rather than making assumptions
- Present financial data clearly with proper formatting (use tables when helpful)
- Explain metrics like P&L, returns, and margins in simple terms
- Be concise but informative
- If a tool fails, explain the issue and suggest alternatives
- For market data queries, use search_instruments first to find the correct instrument ID, then get_quotes or get_ltp

When asked about news or why a stock moved:
- Use search_news to find relevant news articles
- If no results found, use ingest_stock_news to fetch fresh news, then search again
- Cite sources when presenting news information

When presenting holdings or positions:
- Show symbol, quantity, average price, current price, and P&L
- Calculate and highlight total portfolio value and overall P&L
- Identify best and worst performers when relevant
"""


# Re-export for backward compatibility
Message = type("Message", (), {"role": str, "content": str})


def _get_anthropic_client(api_key: str | None = None) -> AsyncAnthropic:
    """Get asynchronous Anthropic client instance."""
    key = api_key or os.getenv("ANTHROPIC_API_KEY")
    if not key:
        raise ValueError("ANTHROPIC_API_KEY not set in environment")
    return Anthropic(api_key=key)


class ClaudeProvider:
    """Claude LLM provider with tool calling support."""

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
    ):
        """Initialize Claude provider.

        Args:
            model: Model name (defaults to config)
            api_key: API key (defaults to environment)
        """
        config = get_config()
        self._model = model or config.claude_model
        self._client: AsyncAnthropic = _get_anthropic_client(api_key)

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
        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": max_tokens,
            "messages": messages,
        }

        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = tools

        response = await self._client.messages.create(**kwargs)

        # Extract content and tool calls
        content_parts: list[str] = []
        tool_calls: list[ToolCall] = []

        for block in response.content:
            if block.type == "text":
                content_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(
                    ToolCall(
                        id=block.id,
                        name=block.name,
                        input=block.input,
                    )
                )

        content = "".join(content_parts)

        return CompletionResponse(
            content=content,
            tool_calls=tool_calls,
            stop_reason=response.stop_reason or "end_turn",
        )

    async def stream(
        self,
        messages: list[dict[str, Any]],
        system: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int = 4096,
    ) -> AsyncIterator[StreamEvent]:
        """Stream a completion response.

        Args:
            messages: Conversation messages
            system: Optional system prompt
            tools: Optional tool definitions
            max_tokens: Maximum tokens to generate

        Yields:
            StreamEvent objects as the response is generated
        """
        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": max_tokens,
            "messages": messages,
        }

        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = tools

        async with self._client.messages.stream(**kwargs) as stream:
            tool_calls: list[ToolCall] = []
            current_text = ""

            async for event in stream:
                if event.type == "content_block_start":
                    block = event.content_block
                    if block.type == "text":
                        current_text = ""
                    elif block.type == "tool_use":
                        tool_calls.append(
                            ToolCall(
                                id=block.id,
                                name=block.name,
                                input={},
                            )
                        )

                elif event.type == "content_block_delta":
                    delta = event.delta
                    if delta.type == "text_delta":
                        current_text += delta.text
                        yield StreamEvent(type="text", text=delta.text)

            # Get the final message
            final_message = await stream.get_final_message()

            # Emit tool calls
            for block in final_message.content:
                if block.type == "tool_use":
                    for tc in tool_calls:
                        if tc.id == block.id:
                            tc.input = block.input
                            yield StreamEvent(type="tool_use", tool_call=tc)

            yield StreamEvent(type="done")


class ClaudeSimpleProvider:
    """Simple Claude provider for basic completions without tool calling."""

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
    ):
        """Initialize simple Claude provider.

        Args:
            model: Model name (defaults to config)
            api_key: API key (defaults to environment)
        """
        config = get_config()
        self._model = model or config.claude_model
        self._client: AsyncAnthropic = _get_anthropic_client(api_key)

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
        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": max_tokens,
            "messages": messages,
        }

        if system:
            kwargs["system"] = system

        response = await self._client.messages.create(**kwargs)

        if not response.content:
            return ""

        return response.content[0].text if hasattr(response.content[0], "text") else ""


class PortfolioAssistant:
    """Claude-powered portfolio assistant with tool calling."""

    def __init__(
        self,
        kite_client: KiteClient,
        provider: Any | None = None,
    ):
        """Initialize portfolio assistant.

        Args:
            kite_client: KiteClient for executing portfolio tools
            provider: Optional LLM provider (defaults to factory provider)
        """
        if provider is None:
            from src.llm.factory import get_llm_provider

            provider = get_llm_provider()

        self._provider = provider
        self._kite = kite_client
        self._history: list[dict[str, Any]] = []
        self._tools = get_all_tools()
        self._pending_tool_calls: list[ToolCall] = []

    def clear_history(self) -> None:
        """Clear conversation history."""
        self._history = []

    async def _execute_tool(self, name: str, args: dict[str, Any]) -> str:
        """Execute a tool and return the result as JSON string."""
        try:
            # Portfolio tools (Kite MCP)
            if name == "get_holdings":
                result = await self._kite.get_holdings()
            elif name == "get_positions":
                result = await self._kite.get_positions()
            elif name == "get_margins":
                result = await self._kite.get_margins(args.get("segment"))
            elif name == "get_quotes":
                result = await self._kite.get_quotes(args.get("instruments", []))
            elif name == "get_ltp":
                result = await self._kite.get_ltp(args.get("instruments", []))
            elif name == "search_instruments":
                result = await self._kite.search_instruments(args.get("query", ""))

            # RAG tools
            elif name == "search_news":
                from src.rag.retriever import search_news

                results = search_news(
                    query=args.get("query", ""),
                    symbol=args.get("symbol"),
                    top_k=min(args.get("top_k", 3), 10),
                )
                result = [
                    {
                        "title": r.title,
                        "content": r.content[:500],  # Truncate for context
                        "source": r.source,
                        "url": r.url,
                        "symbol": r.symbol,
                        "score": round(r.score, 3),
                    }
                    for r in results
                ]

            elif name == "ingest_stock_news":
                from src.data.ingestion import ingest_news

                stats = await ingest_news(
                    symbols=args.get("symbols", []),
                    limit=args.get("limit", 5),
                )
                result = {
                    "articles_fetched": stats.articles_fetched,
                    "chunks_stored": stats.chunks_stored,
                    "errors": stats.errors[:3] if stats.errors else [],
                }

            else:
                return json.dumps({"error": f"Unknown tool: {name}"})

            return json.dumps(result, default=str)
        except Exception as e:
            return json.dumps({"error": str(e)})

    async def chat(self, user_message: str) -> AsyncIterator[StreamEvent]:
        """Send a message and stream the response.

        Handles tool calls automatically - executes tools and continues
        the conversation until the LLM provides a final text response.
        """
        # Add user message to history
        self._history.append({"role": "user", "content": user_message})

        # Check if provider is Claude (native tool calling) or Ollama (prompt-based)
        is_claude = isinstance(self._provider, ClaudeProvider)

        while True:
            if is_claude:
                # Claude: Use native streaming with tool calling
                async for event in self._stream_claude():
                    if event.type == "done":
                        return
                    yield event

                # Check if we need to handle tool calls
                if self._pending_tool_calls:
                    await self._handle_tool_calls()
                    continue
                return
            else:
                # Ollama: Use prompt-based tool calling
                async for event in self._stream_ollama():
                    if event.type == "done":
                        return
                    yield event

                # Check if we need to handle tool calls
                if self._pending_tool_calls:
                    await self._handle_tool_calls()
                    continue
                return

    async def _stream_claude(self) -> AsyncIterator[StreamEvent]:
        """Stream response using Claude provider."""
        self._pending_tool_calls = []
        response_content: list[dict[str, Any]] = []
        accumulated_text = ""

        async for event in self._provider.stream(
            messages=self._history,
            system=SYSTEM_PROMPT,
            tools=self._tools,
            max_tokens=MAX_TOKENS,
        ):
            if event.type == "text":
                accumulated_text += event.text
                yield event
            elif event.type == "tool_use" and event.tool_call:
                self._pending_tool_calls.append(event.tool_call)
                yield event
            elif event.type == "done":
                # Build response content for history
                if accumulated_text:
                    response_content.append({
                        "type": "text",
                        "text": accumulated_text,
                    })

                for tc in self._pending_tool_calls:
                    response_content.append({
                        "type": "tool_use",
                        "id": tc.id,
                        "name": tc.name,
                        "input": tc.input,
                    })

                # Only append to history if we have content
                if response_content:
                    self._history.append({"role": "assistant", "content": response_content})

                if not self._pending_tool_calls:
                    yield event

    async def _stream_ollama(self) -> AsyncIterator[StreamEvent]:
        """Stream response using Ollama provider."""
        self._pending_tool_calls = []
        accumulated_text = ""

        async for event in self._provider.stream(
            messages=self._history,
            system=SYSTEM_PROMPT,
            tools=self._tools,
            max_tokens=MAX_TOKENS,
        ):
            if event.type == "text":
                accumulated_text += event.text
                yield event
            elif event.type == "tool_use" and event.tool_call:
                self._pending_tool_calls.append(event.tool_call)
                yield event
            elif event.type == "done":
                # Build response content for history (text + tool_use blocks)
                response_content: list[dict[str, Any]] = []

                if accumulated_text:
                    response_content.append({
                        "type": "text",
                        "text": accumulated_text,
                    })

                for tc in self._pending_tool_calls:
                    response_content.append({
                        "type": "tool_use",
                        "id": tc.id,
                        "name": tc.name,
                        "input": tc.input,
                    })

                # Only append to history if we have content
                if response_content:
                    self._history.append({
                        "role": "assistant",
                        "content": response_content,
                    })

                if not self._pending_tool_calls:
                    yield event

    async def _handle_tool_calls(self) -> None:
        """Execute pending tool calls and add results to history."""
        tool_results = []

        for tc in self._pending_tool_calls:
            result = await self._execute_tool(tc.name, tc.input)
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tc.id,
                "content": result,
            })

        # Add tool results to history
        self._history.append({"role": "user", "content": tool_results})
        self._pending_tool_calls = []

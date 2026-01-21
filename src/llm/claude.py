"""Claude client with streaming and tool support."""

import json
import os
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from anthropic import Anthropic
from dotenv import load_dotenv

from src.llm.tools import get_all_tools
from src.mcp.kite_client import KiteClient

load_dotenv()

MODEL = "claude-sonnet-4-20250514"
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


@dataclass
class Message:
    """A conversation message."""

    role: str  # "user" or "assistant"
    content: str


@dataclass
class ToolCall:
    """A tool call from Claude."""

    id: str
    name: str
    input: dict[str, Any]


@dataclass
class StreamEvent:
    """An event from the streaming response."""

    type: str  # "text", "tool_use", "done"
    text: str = ""
    tool_call: ToolCall | None = None


class PortfolioAssistant:
    """Claude-powered portfolio assistant with tool calling."""

    def __init__(self, kite_client: KiteClient):
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not set in environment")

        self._anthropic = Anthropic(api_key=api_key)
        self._kite = kite_client
        self._history: list[dict[str, Any]] = []
        self._tools = get_all_tools()

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
        the conversation until Claude provides a final text response.
        """
        # Add user message to history
        self._history.append({"role": "user", "content": user_message})

        while True:
            # Create streaming request
            with self._anthropic.messages.stream(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=SYSTEM_PROMPT,
                tools=self._tools,
                messages=self._history,
            ) as stream:
                response_content: list[dict[str, Any]] = []
                current_text = ""
                tool_calls: list[ToolCall] = []

                for event in stream:
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
                        elif delta.type == "input_json_delta":
                            # Accumulate tool input JSON
                            if tool_calls:
                                # Parse partial JSON as it comes in
                                pass  # We'll get the full input from the final message

                    elif event.type == "message_delta":
                        pass  # Message-level updates

                # Get the final message
                final_message = stream.get_final_message()

                # Process content blocks
                for block in final_message.content:
                    if block.type == "text":
                        response_content.append({"type": "text", "text": block.text})
                    elif block.type == "tool_use":
                        response_content.append({
                            "type": "tool_use",
                            "id": block.id,
                            "name": block.name,
                            "input": block.input,
                        })
                        # Update tool call with full input
                        for tc in tool_calls:
                            if tc.id == block.id:
                                tc.input = block.input
                                yield StreamEvent(type="tool_use", tool_call=tc)

                # Add assistant response to history
                self._history.append({"role": "assistant", "content": response_content})

                # Check if we need to execute tools
                if final_message.stop_reason == "tool_use":
                    # Execute all tool calls and add results
                    tool_results = []
                    for block in final_message.content:
                        if block.type == "tool_use":
                            result = await self._execute_tool(block.name, block.input)
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": result,
                            })

                    # Add tool results to history
                    self._history.append({"role": "user", "content": tool_results})

                    # Continue the loop to get Claude's response to tool results
                    continue

                # No more tool calls - we're done
                yield StreamEvent(type="done")
                break

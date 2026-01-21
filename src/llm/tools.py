"""Tool definitions for Claude to interact with Kite MCP and RAG."""

from typing import Any

# Portfolio tools for Kite MCP
PORTFOLIO_TOOLS: list[dict[str, Any]] = [
    {
        "name": "get_holdings",
        "description": "Fetch the user's portfolio holdings (long-term stocks held in DEMAT account). Returns list of stocks with symbol, quantity, average price, current price, and P&L.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_positions",
        "description": "Fetch current trading positions (intraday and overnight). Returns both 'net' positions (cumulative) and 'day' positions (today's activity).",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_margins",
        "description": "Fetch account margins and available buying power. Shows available cash, used margin, and collateral.",
        "input_schema": {
            "type": "object",
            "properties": {
                "segment": {
                    "type": "string",
                    "description": "Optional segment filter (e.g., 'equity', 'commodity')",
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_quotes",
        "description": "Get real-time market quotes for specific instruments. Returns OHLC, volume, and other market data.",
        "input_schema": {
            "type": "object",
            "properties": {
                "instruments": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of instrument identifiers in format 'EXCHANGE:SYMBOL' (e.g., ['NSE:RELIANCE', 'NSE:TCS'])",
                },
            },
            "required": ["instruments"],
        },
    },
    {
        "name": "get_ltp",
        "description": "Get last traded price (LTP) for specific instruments. Lighter than full quotes.",
        "input_schema": {
            "type": "object",
            "properties": {
                "instruments": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of instrument identifiers in format 'EXCHANGE:SYMBOL' (e.g., ['NSE:RELIANCE', 'NSE:TCS'])",
                },
            },
            "required": ["instruments"],
        },
    },
    {
        "name": "search_instruments",
        "description": "Search for trading instruments by name or symbol. Use this to find the correct instrument identifier before fetching quotes.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query - stock name or symbol (e.g., 'reliance', 'TCS', 'infosys')",
                },
            },
            "required": ["query"],
        },
    },
]


# RAG tools for news search
RAG_TOOLS: list[dict[str, Any]] = [
    {
        "name": "search_news",
        "description": "Search for recent news articles about stocks or market events. Use this to find context about why a stock moved, recent announcements, or market sentiment. Returns relevant news snippets from MoneyControl and Yahoo Finance.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query - what you want to find news about (e.g., 'Reliance quarterly results', 'TCS layoffs', 'IT sector outlook')",
                },
                "symbol": {
                    "type": "string",
                    "description": "Optional stock symbol to filter results (e.g., 'RELIANCE', 'TCS')",
                },
                "top_k": {
                    "type": "integer",
                    "description": "Number of results to return (default: 3, max: 10)",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "ingest_stock_news",
        "description": "Fetch and store the latest news for specific stocks. Use this before searching if the user asks about recent news and you haven't ingested data recently. This updates the news database.",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbols": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of stock symbols to fetch news for (e.g., ['RELIANCE', 'TCS'])",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max articles per source per symbol (default: 5)",
                },
            },
            "required": ["symbols"],
        },
    },
]


def get_all_tools() -> list[dict[str, Any]]:
    """Get all available tool definitions."""
    return PORTFOLIO_TOOLS + RAG_TOOLS

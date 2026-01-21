"""Stock Research Agent workflow using LangGraph."""

import os
import re
from typing import Any

from anthropic import Anthropic
from dotenv import load_dotenv
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph

from src.agents.tools.news_tools import (
    ensure_news_indexed,
    get_news_context_string,
    search_stock_news,
)
from src.mcp.kite_client import KiteClient

load_dotenv()

MODEL = "claude-sonnet-4-20250514"


def _get_anthropic() -> Anthropic:
    """Get Anthropic client."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set")
    return Anthropic(api_key=api_key)


def extract_symbol_from_query(query: str) -> str | None:
    """Extract stock symbol from natural language query.

    Examples:
        "Tell me about Reliance" -> "RELIANCE"
        "Research TCS stock" -> "TCS"
        "What's happening with INFY?" -> "INFY"
    """
    query_upper = query.upper()

    # Common Indian stock symbols
    known_symbols = [
        "RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK", "HINDUNILVR",
        "ITC", "SBIN", "BHARTIARTL", "KOTAKBANK", "LT", "AXISBANK",
        "ASIANPAINT", "MARUTI", "TITAN", "SUNPHARMA", "ULTRACEMCO",
        "WIPRO", "HCLTECH", "TECHM", "BAJFINANCE", "BAJAJFINSV",
        "NESTLEIND", "POWERGRID", "NTPC", "ONGC", "TATASTEEL",
        "JSWSTEEL", "COALINDIA", "ADANIENT", "ADANIPORTS", "GABRIEL",
        "TATAMOTORS", "M&M", "HEROMOTOCO", "EICHERMOT", "BAJAJ-AUTO",
    ]

    # Check for known symbols in query
    for symbol in known_symbols:
        if symbol in query_upper:
            return symbol

    # Try to extract capitalized words that might be symbols
    words = re.findall(r'\b[A-Z]{2,}(?:-[A-Z]+)?\b', query_upper)
    for word in words:
        if word not in ["THE", "AND", "FOR", "ABOUT", "WHAT", "TELL", "SHOW", "GET"]:
            return word

    # Try to find company names and map to symbols
    name_to_symbol = {
        "RELIANCE": "RELIANCE",
        "TATA CONSULTANCY": "TCS",
        "INFOSYS": "INFY",
        "HDFC BANK": "HDFCBANK",
        "ICICI BANK": "ICICIBANK",
        "HINDUSTAN UNILEVER": "HINDUNILVR",
        "STATE BANK": "SBIN",
        "BHARTI AIRTEL": "BHARTIARTL",
        "KOTAK": "KOTAKBANK",
        "LARSEN": "LT",
        "AXIS BANK": "AXISBANK",
        "ASIAN PAINTS": "ASIANPAINT",
        "MARUTI": "MARUTI",
        "TITAN": "TITAN",
        "SUN PHARMA": "SUNPHARMA",
        "WIPRO": "WIPRO",
        "HCL": "HCLTECH",
        "TECH MAHINDRA": "TECHM",
        "BAJAJ FINANCE": "BAJFINANCE",
        "NESTLE": "NESTLEIND",
        "TATA STEEL": "TATASTEEL",
        "JSW STEEL": "JSWSTEEL",
        "COAL INDIA": "COALINDIA",
        "ADANI": "ADANIENT",
        "GABRIEL": "GABRIEL",
        "TATA MOTORS": "TATAMOTORS",
        "MAHINDRA": "M&M",
        "HERO": "HEROMOTOCO",
        "EICHER": "EICHERMOT",
        "BAJAJ AUTO": "BAJAJ-AUTO",
    }

    for name, symbol in name_to_symbol.items():
        if name in query_upper:
            return symbol

    return None


# Node functions


async def extract_symbol_node(
    state: dict[str, Any],
    config: RunnableConfig,
) -> dict[str, Any]:
    """Node: Extract stock symbol from query."""
    query = state.get("query", "")

    # Check if symbol was already provided
    symbol = state.get("symbol", "")

    if not symbol:
        symbol = extract_symbol_from_query(query)

    if not symbol:
        return {
            "error": "Could not identify stock symbol from query. Please specify a stock symbol.",
            "steps_completed": state.get("steps_completed", []) + ["extract_symbol"],
        }

    return {
        "symbol": symbol.upper(),
        "steps_completed": state.get("steps_completed", []) + ["extract_symbol"],
    }


async def check_holdings_node(
    state: dict[str, Any],
    config: RunnableConfig,
) -> dict[str, Any]:
    """Node: Check if user holds this stock."""
    client: KiteClient = config["configurable"]["kite_client"]
    symbol = state.get("symbol", "")

    try:
        holdings = await client.get_holdings()

        # Find the stock in holdings
        holding = None
        for h in holdings:
            if h.get("tradingsymbol", "").upper() == symbol.upper():
                holding = h
                break

        return {
            "holdings_position": holding,
            "steps_completed": state.get("steps_completed", []) + ["check_holdings"],
        }
    except Exception as e:
        return {
            "holdings_position": None,
            "steps_completed": state.get("steps_completed", []) + ["check_holdings"],
        }


async def get_price_node(
    state: dict[str, Any],
    config: RunnableConfig,
) -> dict[str, Any]:
    """Node: Get current price and market data."""
    client: KiteClient = config["configurable"]["kite_client"]
    symbol = state.get("symbol", "")

    try:
        # Try NSE first, then BSE
        instruments = [f"NSE:{symbol}", f"BSE:{symbol}"]
        quotes = await client.get_quotes(instruments)

        # Get the first valid quote
        current_price = None
        for inst in instruments:
            if inst in quotes:
                current_price = quotes[inst]
                break

        return {
            "current_price": current_price,
            "steps_completed": state.get("steps_completed", []) + ["get_price"],
        }
    except Exception as e:
        return {
            "current_price": None,
            "steps_completed": state.get("steps_completed", []) + ["get_price"],
        }


async def fetch_news_node(state: dict[str, Any]) -> dict[str, Any]:
    """Node: Fetch news about the stock."""
    symbol = state.get("symbol", "")

    if not symbol:
        return {
            "news_articles": [],
            "steps_completed": state.get("steps_completed", []) + ["fetch_news"],
        }

    # Ensure news is indexed
    await ensure_news_indexed([symbol])

    # Search for news
    news_articles = search_stock_news([symbol], top_k=5)

    return {
        "news_articles": news_articles,
        "steps_completed": state.get("steps_completed", []) + ["fetch_news"],
    }


def generate_report_node(state: dict[str, Any]) -> dict[str, Any]:
    """Node: Generate research report using Claude."""
    symbol = state.get("symbol", "")
    query = state.get("query", "")
    holdings_position = state.get("holdings_position")
    current_price = state.get("current_price")
    news_articles = state.get("news_articles", [])

    if state.get("error"):
        return {
            "research_report": f"Unable to research: {state['error']}",
            "steps_completed": state.get("steps_completed", []) + ["generate_report"],
        }

    # Format holdings info
    holdings_text = "You do not hold this stock."
    if holdings_position:
        qty = holdings_position.get("quantity", 0)
        avg_price = holdings_position.get("average_price", 0)
        pnl = holdings_position.get("pnl", 0)
        holdings_text = f"""You hold this stock:
- Quantity: {qty}
- Average Price: ₹{avg_price:.2f}
- P&L: ₹{pnl:.2f}"""

    # Format price info
    price_text = "Price data not available."
    if current_price:
        ltp = current_price.get("last_price", 0)
        change = current_price.get("change", 0)
        change_pct = current_price.get("change_percent", 0) or current_price.get("pct_change", 0)
        ohlc = current_price.get("ohlc", {})

        price_text = f"""Current Market Data:
- Last Price: ₹{ltp:.2f}
- Change: ₹{change:.2f} ({change_pct:.2f}%)
- Open: ₹{ohlc.get('open', 0):.2f}
- High: ₹{ohlc.get('high', 0):.2f}
- Low: ₹{ohlc.get('low', 0):.2f}"""

    # Format news
    news_text = get_news_context_string(news_articles)

    prompt = f"""Generate a concise research report for {symbol} based on the user's query.

User Query: {query}

{holdings_text}

{price_text}

Recent News:
{news_text}

Provide a research report that:
1. Summarizes the current state of the stock
2. Mentions user's position if they hold it
3. Highlights key news and developments
4. Provides brief outlook or observations

Keep it concise (under 300 words) and actionable."""

    try:
        anthropic = _get_anthropic()
        response = anthropic.messages.create(
            model=MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )

        report = response.content[0].text

    except Exception as e:
        report = f"Error generating report: {e}"

    return {
        "research_report": report,
        "steps_completed": state.get("steps_completed", []) + ["generate_report"],
    }


def should_continue(state: dict[str, Any]) -> str:
    """Determine if workflow should continue or end."""
    if state.get("error"):
        return "generate_report"
    return "continue"


def create_stock_research_graph() -> StateGraph:
    """Create the Stock Research workflow graph."""
    workflow = StateGraph(dict)

    # Add nodes
    workflow.add_node("extract_symbol", extract_symbol_node)
    workflow.add_node("check_holdings", check_holdings_node)
    workflow.add_node("get_price", get_price_node)
    workflow.add_node("fetch_news", fetch_news_node)
    workflow.add_node("generate_report", generate_report_node)

    # Define edges
    workflow.set_entry_point("extract_symbol")

    workflow.add_conditional_edges(
        "extract_symbol",
        should_continue,
        {
            "continue": "check_holdings",
            "generate_report": "generate_report",
        },
    )

    workflow.add_edge("check_holdings", "get_price")
    workflow.add_edge("get_price", "fetch_news")
    workflow.add_edge("fetch_news", "generate_report")
    workflow.add_edge("generate_report", END)

    return workflow.compile()


class StockResearchAgent:
    """High-level interface for Stock Research workflow."""

    def __init__(self, kite_client: KiteClient):
        self._client = kite_client
        self._graph = create_stock_research_graph()

    async def research(
        self,
        query: str,
        symbol: str | None = None,
    ) -> str:
        """Run stock research.

        Args:
            query: User's query
            symbol: Optional explicit symbol (if not provided, extracted from query)

        Returns:
            Research report as string
        """
        initial_state = {
            "query": query,
            "symbol": symbol or "",
            "holdings_position": None,
            "current_price": None,
            "news_articles": [],
            "research_report": "",
            "error": None,
            "steps_completed": [],
        }

        config = {"configurable": {"kite_client": self._client}}

        final_state = await self._graph.ainvoke(initial_state, config)

        return final_state.get("research_report", "No report generated.")


async def run_stock_research(
    kite_client: KiteClient,
    query: str,
    symbol: str | None = None,
) -> str:
    """Run stock research workflow."""
    agent = StockResearchAgent(kite_client)
    return await agent.research(query, symbol)

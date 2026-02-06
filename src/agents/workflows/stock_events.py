"""Stock Events Agent workflow using LangGraph."""

import operator
import re
from typing import Annotated, Any, TypedDict

import structlog
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph

from src.agents.tools.symbol_tools import extract_symbol
from src.data.scrapers.bse import BSEScraper

log = structlog.get_logger()

_PORTFOLIO_KEYWORDS = re.compile(
    r"(my\s+)?(portfolio|holdings|stocks|all\s+stocks)", re.IGNORECASE
)


def replace_value(current: Any, new: Any) -> Any:
    """Reducer that replaces the current value with the new one."""
    return new


class StockEventsState(TypedDict):
    """State schema for stock events workflow."""

    query: str
    symbol: Annotated[str, replace_value]
    symbols: Annotated[list[str], replace_value]
    events: Annotated[list[dict], replace_value]
    formatted_output: Annotated[str, replace_value]
    error: Annotated[str | None, replace_value]
    steps_completed: Annotated[list, operator.add]


async def extract_symbol_node(state: StockEventsState, config: RunnableConfig) -> dict[str, Any]:
    """Node: Extract stock symbol from query, or detect portfolio-wide request."""
    symbol = state.get("symbol", "")
    query = state.get("query", "")

    if symbol:
        return {
            "symbol": symbol.upper(),
            "symbols": [symbol.upper()],
            "steps_completed": ["extract_symbol"],
        }

    extracted = extract_symbol(query)
    if extracted:
        return {
            "symbol": extracted.upper(),
            "symbols": [extracted.upper()],
            "steps_completed": ["extract_symbol"],
        }

    # Check if this is a portfolio-wide request
    if _PORTFOLIO_KEYWORDS.search(query):
        return {
            "symbol": "__PORTFOLIO__",
            "symbols": [],
            "steps_completed": ["extract_symbol"],
        }

    return {
        "error": "Could not identify stock symbol. Please specify a stock symbol (e.g., 'events for RELIANCE').",
        "steps_completed": ["extract_symbol"],
    }


async def resolve_portfolio_node(state: StockEventsState, config: RunnableConfig) -> dict[str, Any]:
    """Node: Resolve portfolio holdings to get symbols list."""
    from src.mcp.kite_client import KiteClient

    if state.get("symbol") != "__PORTFOLIO__":
        # Single-stock query, already resolved
        return {"steps_completed": ["resolve_portfolio"]}

    client: KiteClient | None = config.get("configurable", {}).get("kite_client")
    if not client:
        return {
            "error": "Cannot fetch portfolio events: not connected to Kite. Use 'login' first, or specify a stock symbol.",
            "steps_completed": ["resolve_portfolio"],
        }

    try:
        holdings = await client.get_holdings()
        symbols = [
            h.get("tradingsymbol", "").upper()
            for h in holdings
            if h.get("tradingsymbol")
        ]
        if not symbols:
            return {
                "error": "No holdings found in your portfolio.",
                "steps_completed": ["resolve_portfolio"],
            }
        return {
            "symbols": symbols,
            "steps_completed": ["resolve_portfolio"],
        }
    except Exception as e:
        log.error("holdings_fetch_error", exc_info=True)
        return {
            "error": f"Failed to fetch portfolio holdings: {e}",
            "steps_completed": ["resolve_portfolio"],
        }


async def fetch_events_node(state: StockEventsState, config: RunnableConfig) -> dict[str, Any]:
    """Node: Fetch corporate events from BSE for one or more symbols."""
    if state.get("error"):
        return {"events": [], "steps_completed": ["fetch_events"]}

    symbols = state.get("symbols", [])
    if not symbols:
        return {
            "events": [],
            "error": "No symbols to fetch events for.",
            "steps_completed": ["fetch_events"],
        }

    # Limit per-stock when doing portfolio-wide to keep output manageable
    is_multi = len(symbols) > 1
    per_stock_limit = 5 if is_multi else 20

    scraper = BSEScraper()
    try:
        all_events: list[dict] = []
        for sym in symbols:
            raw_events = await scraper.get_corporate_events(sym, limit=per_stock_limit)
            for e in raw_events:
                all_events.append({
                    "title": e.title,
                    "category": e.category,
                    "date": e.date.strftime("%Y-%m-%d") if e.date else "N/A",
                    "url": e.url,
                    "symbol": e.symbol,
                })

        if not all_events:
            label = ", ".join(symbols[:5])
            if len(symbols) > 5:
                label += f" and {len(symbols) - 5} more"
            return {
                "events": [],
                "error": f"No corporate events found on BSE for: {label}.",
                "steps_completed": ["fetch_events"],
            }

        # Sort by date descending
        all_events.sort(key=lambda e: e.get("date", ""), reverse=True)
        return {"events": all_events, "steps_completed": ["fetch_events"]}
    except Exception as e:
        log.error("events_fetch_error", exc_info=True)
        return {
            "events": [],
            "error": f"Failed to fetch events: {e}",
            "steps_completed": ["fetch_events"],
        }
    finally:
        await scraper.close()


async def format_output_node(state: StockEventsState, config: RunnableConfig) -> dict[str, Any]:
    """Node: Format events into a summary string."""
    events = state.get("events", [])
    symbol = state.get("symbol", "")
    error = state.get("error")

    if error:
        return {
            "formatted_output": error,
            "steps_completed": ["format_output"],
        }

    is_portfolio = symbol == "__PORTFOLIO__"
    header = "Corporate Events for Portfolio" if is_portfolio else f"Corporate Events for {symbol}"
    lines = [f"**{header}** ({len(events)} found)\n"]
    for i, e in enumerate(events, 1):
        cat = e["category"].replace("_", " ").title()
        sym_prefix = f"[{e['symbol']}] " if is_portfolio else ""
        lines.append(f"{i}. {sym_prefix}[{cat}] {e['title']} ({e['date']})")

    return {
        "formatted_output": "\n".join(lines),
        "steps_completed": ["format_output"],
    }


def should_continue(state: StockEventsState) -> str:
    """Determine if workflow should continue or skip to format."""
    if state.get("error"):
        return "format_output"
    return "continue"


def create_stock_events_graph() -> StateGraph:
    """Create the Stock Events workflow graph."""
    workflow = StateGraph(StockEventsState)

    workflow.add_node("extract_symbol", extract_symbol_node)
    workflow.add_node("resolve_portfolio", resolve_portfolio_node)
    workflow.add_node("fetch_events", fetch_events_node)
    workflow.add_node("format_output", format_output_node)

    workflow.set_entry_point("extract_symbol")

    workflow.add_conditional_edges(
        "extract_symbol",
        should_continue,
        {
            "continue": "resolve_portfolio",
            "format_output": "format_output",
        },
    )

    workflow.add_conditional_edges(
        "resolve_portfolio",
        should_continue,
        {
            "continue": "fetch_events",
            "format_output": "format_output",
        },
    )

    workflow.add_edge("fetch_events", "format_output")
    workflow.add_edge("format_output", END)

    return workflow.compile()


class StockEventsAgent:
    """High-level interface for Stock Events workflow."""

    def __init__(self, kite_client: Any = None):
        self._client = kite_client
        self._graph = create_stock_events_graph()

    def _config(self) -> dict:
        cfg: dict[str, Any] = {}
        if self._client:
            cfg["configurable"] = {"kite_client": self._client}
        return cfg

    async def get_events(
        self, query: str, symbol: str | None = None
    ) -> list[dict]:
        """Run stock events workflow.

        Args:
            query: User's query
            symbol: Optional explicit symbol

        Returns:
            List of event dicts with title, category, date, url, symbol
        """
        initial_state: dict[str, Any] = {
            "query": query,
            "symbol": symbol or "",
            "symbols": [],
            "events": [],
            "formatted_output": "",
            "error": None,
            "steps_completed": [],
        }

        final_state = await self._graph.ainvoke(initial_state, self._config())
        return final_state.get("events", [])

    async def get_events_formatted(
        self, query: str, symbol: str | None = None
    ) -> str:
        """Run workflow and return formatted string output."""
        initial_state: dict[str, Any] = {
            "query": query,
            "symbol": symbol or "",
            "symbols": [],
            "events": [],
            "formatted_output": "",
            "error": None,
            "steps_completed": [],
        }

        final_state = await self._graph.ainvoke(initial_state, self._config())
        return final_state.get("formatted_output", "No events found.")

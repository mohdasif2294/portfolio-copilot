"""Market Context Agent workflow using LangGraph."""

import operator
from typing import Annotated, Any, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph

from src.agents.tools.news_tools import (
    ensure_news_indexed,
    get_news_context_string,
    search_stock_news,
)
from src.mcp.kite_client import KiteClient


def replace_value(current: Any, new: Any) -> Any:
    """Reducer that replaces the current value with the new one."""
    return new


class MarketContextState(TypedDict):
    """State schema for market context workflow."""

    query: str
    portfolio_pnl: Annotated[dict | None, replace_value]
    movers: Annotated[list, replace_value]
    market_news: Annotated[list, replace_value]
    context_report: Annotated[str, replace_value]
    error: Annotated[str | None, replace_value]
    steps_completed: Annotated[list, operator.add]


# Node functions


async def fetch_portfolio_pnl_node(
    state: MarketContextState,
    config: RunnableConfig,
) -> dict[str, Any]:
    """Node: Fetch portfolio and calculate today's P&L."""
    client: KiteClient = config["configurable"]["kite_client"]

    try:
        holdings = await client.get_holdings()

        if not holdings:
            return {
                "error": "No holdings found in portfolio.",
                "steps_completed": ["fetch_portfolio"],
            }

        # Calculate P&L metrics
        total_value = 0.0
        total_pnl = 0.0
        day_pnl = 0.0

        for h in holdings:
            qty = h.get("quantity", 0)
            last_price = h.get("last_price", 0)
            pnl = h.get("pnl", 0)
            day_change = h.get("day_change", 0)

            total_value += qty * last_price
            total_pnl += pnl
            day_pnl += day_change * qty if day_change else 0

        portfolio_pnl = {
            "holdings": holdings,
            "total_value": total_value,
            "total_pnl": total_pnl,
            "day_pnl": day_pnl,
            "num_holdings": len(holdings),
        }

        return {
            "portfolio_pnl": portfolio_pnl,
            "steps_completed": ["fetch_portfolio"],
        }

    except Exception as e:
        return {
            "error": f"Failed to fetch portfolio: {e}",
            "steps_completed": ["fetch_portfolio"],
        }


def identify_movers_node(state: MarketContextState) -> dict[str, Any]:
    """Node: Identify stocks that moved the most today."""
    portfolio_pnl = state.get("portfolio_pnl") or {}
    holdings = portfolio_pnl.get("holdings", [])

    if not holdings:
        return {
            "movers": [],
            "steps_completed": ["identify_movers"],
        }

    # Calculate day change for each holding
    movers = []
    for h in holdings:
        symbol = h.get("tradingsymbol", "")
        day_change_pct = h.get("day_change_percentage", 0)
        last_price = h.get("last_price", 0)
        qty = h.get("quantity", 0)
        pnl = h.get("pnl", 0)

        movers.append({
            "symbol": symbol,
            "day_change_pct": day_change_pct,
            "last_price": last_price,
            "quantity": qty,
            "total_pnl": pnl,
            "day_impact": day_change_pct * qty * last_price / 100 if last_price else 0,
        })

    # Sort by absolute day change percentage
    movers.sort(key=lambda x: abs(x["day_change_pct"]), reverse=True)

    # Get top movers (both gainers and losers)
    top_movers = movers[:5]

    return {
        "movers": top_movers,
        "steps_completed": ["identify_movers"],
    }


async def fetch_market_news_node(state: MarketContextState) -> dict[str, Any]:
    """Node: Fetch market and sector news."""
    movers = state.get("movers", [])

    # Get symbols of top movers
    symbols = [m["symbol"] for m in movers[:3]]

    if not symbols:
        # Search for general market news
        symbols = ["NIFTY", "SENSEX"]

    # Ensure news is indexed
    await ensure_news_indexed(symbols)

    # Search for news about movers
    mover_news = search_stock_news(symbols, top_k=2)

    # Also search for general market context from query
    from src.rag.retriever import get_retriever
    retriever = get_retriever()

    # Search for market-related terms
    market_terms = ["market", "nifty", "sensex", "sector", "FII", "DII"]
    market_news = []

    for term in market_terms:
        results = retriever.search(term, top_k=2)
        for r in results:
            market_news.append({
                "symbol": term.upper(),
                "title": r.title,
                "content": r.content[:300],
                "source": r.source,
                "url": r.url,
                "score": r.score,
            })

    # Combine and deduplicate
    all_news = mover_news + market_news
    seen_titles = set()
    unique_news = []
    for n in all_news:
        if n["title"] not in seen_titles:
            seen_titles.add(n["title"])
            unique_news.append(n)

    return {
        "market_news": unique_news[:8],
        "steps_completed": ["fetch_news"],
    }


async def generate_context_node(state: MarketContextState) -> dict[str, Any]:
    """Node: Generate market context explanation using LLM."""
    query = state.get("query", "")
    portfolio_pnl = state.get("portfolio_pnl") or {}
    movers = state.get("movers", [])
    market_news = state.get("market_news", [])

    if state.get("error"):
        return {
            "context_report": f"Unable to analyze: {state['error']}",
            "steps_completed": ["generate_context"],
        }

    # Format portfolio summary
    total_value = portfolio_pnl.get("total_value", 0)
    total_pnl = portfolio_pnl.get("total_pnl", 0)
    day_pnl = portfolio_pnl.get("day_pnl", 0)
    num_holdings = portfolio_pnl.get("num_holdings", 0)

    portfolio_text = f"""Portfolio Summary:
- Total Value: ₹{total_value:,.2f}
- Overall P&L: ₹{total_pnl:,.2f}
- Today's Change: ₹{day_pnl:,.2f}
- Holdings: {num_holdings} stocks"""

    # Format movers
    movers_text = "Top Movers Today:\n"
    for m in movers[:5]:
        direction = "↑" if m["day_change_pct"] >= 0 else "↓"
        movers_text += f"- {m['symbol']}: {direction} {abs(m['day_change_pct']):.2f}%\n"

    # Format news
    news_text = get_news_context_string(market_news)

    prompt = f"""Explain the market context for this portfolio based on the user's query.

User Query: {query}

{portfolio_text}

{movers_text}

Recent Market News:
{news_text}

Provide a clear explanation that:
1. Addresses the user's specific question
2. Explains why the portfolio/stocks moved (based on news if available)
3. Highlights any sector or market-wide trends
4. Correlates stock movements with relevant news
5. Provides brief market outlook

Keep it concise (under 350 words) and insightful."""

    try:
        from src.llm.factory import get_simple_provider

        provider = get_simple_provider()
        report = await provider.complete(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024,
        )

        if not report:
            report = "Error: Empty response from AI model"

    except Exception as e:
        report = f"Error generating context: {e}"

    return {
        "context_report": report,
        "steps_completed": ["generate_context"],
    }


def should_continue(state: MarketContextState) -> str:
    """Determine if workflow should continue or end."""
    if state.get("error"):
        return "generate_context"
    return "continue"


def create_market_context_graph() -> StateGraph:
    """Create the Market Context workflow graph."""
    workflow = StateGraph(MarketContextState)

    # Add nodes
    workflow.add_node("fetch_portfolio", fetch_portfolio_pnl_node)
    workflow.add_node("identify_movers", identify_movers_node)
    workflow.add_node("fetch_news", fetch_market_news_node)
    workflow.add_node("generate_context", generate_context_node)

    # Define edges
    workflow.set_entry_point("fetch_portfolio")

    workflow.add_conditional_edges(
        "fetch_portfolio",
        should_continue,
        {
            "continue": "identify_movers",
            "generate_context": "generate_context",
        },
    )

    workflow.add_edge("identify_movers", "fetch_news")
    workflow.add_edge("fetch_news", "generate_context")
    workflow.add_edge("generate_context", END)

    return workflow.compile()


class MarketContextAgent:
    """High-level interface for Market Context workflow."""

    def __init__(self, kite_client: KiteClient):
        self._client = kite_client
        self._graph = create_market_context_graph()

    async def explain(self, query: str) -> str:
        """Explain market context for portfolio.

        Args:
            query: User's query about market/portfolio movement

        Returns:
            Context explanation as string
        """
        initial_state = {
            "query": query,
            "portfolio_pnl": None,
            "movers": [],
            "market_news": [],
            "context_report": "",
            "error": None,
            "steps_completed": [],
        }

        config = {"configurable": {"kite_client": self._client}}

        final_state = await self._graph.ainvoke(initial_state, config)

        return final_state.get("context_report", "No context generated.")


async def run_market_context(
    kite_client: KiteClient,
    query: str,
) -> str:
    """Run market context workflow."""
    agent = MarketContextAgent(kite_client)
    return await agent.explain(query)

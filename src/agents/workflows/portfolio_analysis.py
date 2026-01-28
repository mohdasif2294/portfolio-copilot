"""Portfolio Analysis Agent workflow using LangGraph."""

import operator
from typing import Annotated, Any, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph

from src.agents.tools.news_tools import (
    ensure_news_indexed,
    get_news_context_string,
    search_stock_news,
)
from src.agents.tools.portfolio_tools import analyze_performers, fetch_holdings
from src.mcp.kite_client import KiteClient


# Define state schema with reducers for proper state propagation
def replace_value(current: Any, new: Any) -> Any:
    """Reducer that replaces the current value with the new one."""
    return new


class PortfolioState(TypedDict):
    """State schema for portfolio analysis workflow."""

    query: str
    analysis_type: str
    holdings: Annotated[list, replace_value]
    total_value: Annotated[float, replace_value]
    total_pnl: Annotated[float, replace_value]
    target_stocks: Annotated[list, replace_value]
    news_context: Annotated[list, replace_value]
    insights: Annotated[str, replace_value]
    error: Annotated[str | None, replace_value]
    steps_completed: Annotated[list, operator.add]  # Accumulate steps



# Node functions for the workflow


async def fetch_portfolio_node(
    state: PortfolioState,
    config: RunnableConfig,
) -> dict[str, Any]:
    """Node: Fetch portfolio holdings."""
    client: KiteClient | None = config.get("configurable", {}).get("kite_client")
    if client is None:
        raise RuntimeError(
            "Missing required configuration: 'configurable.kite_client' must be provided"
        )

    result = await fetch_holdings(client)

    if result["error"]:
        return {
            "error": result["error"],
            "steps_completed": ["fetch_portfolio"],
        }

    return {
        "holdings": result["holdings"],
        "total_value": result["total_value"],
        "total_pnl": result["total_pnl"],
        "steps_completed": ["fetch_portfolio"],
    }


def analyze_performers_node(state: PortfolioState) -> dict[str, Any]:
    """Node: Identify best/worst performing stocks."""
    holdings = state.get("holdings", [])
    analysis_type = state.get("analysis_type", "worst")

    if not holdings:
        return {
            "target_stocks": [],
            "steps_completed": ["analyze_performers"],
        }

    target_stocks = analyze_performers(holdings, analysis_type, top_n=3)

    return {
        "target_stocks": target_stocks,
        "steps_completed": ["analyze_performers"],
    }


async def fetch_news_node(state: PortfolioState) -> dict[str, Any]:
    """Node: Fetch and search news for target stocks."""
    target_stocks = state.get("target_stocks", [])

    if not target_stocks:
        return {
            "news_context": [],
            "steps_completed": ["fetch_news"],
        }

    symbols = [s["symbol"] for s in target_stocks]

    # Ensure news is indexed
    await ensure_news_indexed(symbols)

    # Search for news
    news_articles = search_stock_news(symbols, top_k=2)

    return {
        "news_context": news_articles,
        "steps_completed": ["fetch_news"],
    }


async def generate_insights_node(state: PortfolioState) -> dict[str, Any]:
    """Node: Generate insights using LLM."""
    holdings = state.get("holdings", [])
    target_stocks = state.get("target_stocks", [])
    news_context = state.get("news_context", [])
    analysis_type = state.get("analysis_type", "worst")
    total_value = state.get("total_value", 0)
    total_pnl = state.get("total_pnl", 0)
    query = state.get("query", "")

    if state.get("error"):
        return {
            "insights": f"Unable to analyze portfolio: {state['error']}",
            "steps_completed": ["generate_insights"],
        }

    if not holdings:
        return {
            "insights": "No holdings found in your portfolio.",
            "steps_completed": ["generate_insights"],
        }

    # Format data for LLM
    performers_text = ""
    for i, stock in enumerate(target_stocks, 1):
        performers_text += (
            f"{i}. {stock['symbol']}: "
            f"Return {stock['return_pct']:.1f}%, "
            f"P&L ₹{stock['pnl']:.2f}, "
            f"Qty {stock['quantity']}\n"
        )

    news_text = get_news_context_string(news_context)

    prompt = f"""Analyze this portfolio based on the user's query.

User Query: {query}

Portfolio Summary:
- Total Value: ₹{total_value:,.2f}
- Total P&L: ₹{total_pnl:,.2f}
- Number of Holdings: {len(holdings)}

{analysis_type.title()} Performing Stocks:
{performers_text}

Recent News Context:
{news_text}

Provide a concise analysis that:
1. Summarizes the {analysis_type} performers and their returns
2. Explains possible reasons based on news (if available)
3. Gives actionable insights or observations

Keep the response focused and under 300 words."""

    try:
        from src.llm.factory import get_simple_provider

        provider = get_simple_provider()
        insights = await provider.complete(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024,
        )

        if not insights:
            insights = "Error: Empty response from AI model"

    except Exception as e:
        insights = f"Error generating insights: {e}"

    return {
        "insights": insights,
        "steps_completed": ["generate_insights"],
    }


def should_continue(state: PortfolioState) -> str:
    """Determine if workflow should continue or end."""
    if state.get("error"):
        return "generate_insights"  # Go straight to insights to report error
    return "continue"


def create_portfolio_analysis_graph() -> StateGraph:
    """Create the Portfolio Analysis workflow graph."""
    # Define the graph with typed state schema for proper state propagation
    workflow = StateGraph(PortfolioState)

    # Add nodes
    workflow.add_node("fetch_portfolio", fetch_portfolio_node)
    workflow.add_node("analyze_performers", analyze_performers_node)
    workflow.add_node("fetch_news", fetch_news_node)
    workflow.add_node("generate_insights", generate_insights_node)

    # Define edges
    workflow.set_entry_point("fetch_portfolio")

    workflow.add_conditional_edges(
        "fetch_portfolio",
        should_continue,
        {
            "continue": "analyze_performers",
            "generate_insights": "generate_insights",
        },
    )

    workflow.add_edge("analyze_performers", "fetch_news")
    workflow.add_edge("fetch_news", "generate_insights")
    workflow.add_edge("generate_insights", END)

    return workflow.compile()


class PortfolioAnalysisAgent:
    """High-level interface for Portfolio Analysis workflow."""

    def __init__(self, kite_client: KiteClient):
        self._client = kite_client
        self._graph = create_portfolio_analysis_graph()

    async def analyze(
        self,
        query: str,
        analysis_type: str = "worst",
    ) -> str:
        """Run portfolio analysis.

        Args:
            query: User's query
            analysis_type: "worst", "best", or "all"

        Returns:
            Analysis insights as string
        """
        initial_state = {
            "query": query,
            "analysis_type": analysis_type,
            "holdings": [],
            "total_value": 0.0,
            "total_pnl": 0.0,
            "target_stocks": [],
            "news_context": [],
            "insights": "",
            "error": None,
            "steps_completed": [],
        }

        config = {"configurable": {"kite_client": self._client}}

        # Run the workflow
        final_state = await self._graph.ainvoke(initial_state, config)

        return final_state.get("insights", "No insights generated.")

    def detect_analysis_type(self, query: str) -> str:
        """Detect analysis type from query."""
        query_lower = query.lower()

        if any(word in query_lower for word in ["worst", "losing", "loss", "down", "decline", "poor"]):
            return "worst"
        elif any(word in query_lower for word in ["best", "top", "winning", "gain", "up", "good"]):
            return "best"
        else:
            return "worst"  # Default


# Convenience function
async def run_portfolio_analysis(
    kite_client: KiteClient,
    query: str,
) -> str:
    """Run portfolio analysis workflow.

    Args:
        kite_client: Connected Kite MCP client
        query: User's query

    Returns:
        Analysis insights
    """
    agent = PortfolioAnalysisAgent(kite_client)
    analysis_type = agent.detect_analysis_type(query)
    return await agent.analyze(query, analysis_type)
